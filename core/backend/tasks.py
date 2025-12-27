from celery import shared_task
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
import requests
from django.db import transaction
from yaml import safe_load
from yaml.error import YAMLError

from backend.models import (
    Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter
)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_email_task(self, subject: str, message: str, recipient_list: list[str]):
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=recipient_list,
        fail_silently=False,
    )


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, retry_kwargs={"max_retries": 3})
def import_shop_yaml_task(self, shop_id: int, url: str):
    # 1) скачали YAML (это можно делать вне транзакции)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Не удалось скачать YAML: {e}")

    # 2) распарсили YAML (тоже вне транзакции)
    try:
        data = safe_load(resp.content)
    except YAMLError:
        raise RuntimeError("Файл не является корректным YAML")

    if not isinstance(data, dict):
        raise RuntimeError("Некорректная структура YAML")

    for key in ("shop", "categories", "goods"):
        if key not in data:
            raise RuntimeError(f"В YAML нет ключа '{key}'")

    # 3) Всё, что с БД — внутрь atomic
    with transaction.atomic():
        try:
            shop = Shop.objects.select_for_update().get(id=shop_id)
        except ObjectDoesNotExist:
            raise RuntimeError("Shop not found")

        # обновим имя магазина (по yaml)
        if shop.name != data["shop"]:
            shop.name = data["shop"]
            shop.save(update_fields=["name"])

        # категории
        shop.categories.clear()

        cat_map = {}
        for c in (data.get("categories") or []):
            cid = c.get("id")
            cname = (c.get("name") or "").strip()
            if cid is None or not cname:
                continue

            category_obj, _ = Category.objects.get_or_create(name=cname)
            category_obj.shops.add(shop)
            cat_map[cid] = category_obj

        # очистим старые офферы магазина
        ProductInfo.objects.filter(shop=shop).delete()

        # товары
        for item in (data.get("goods") or []):
            external_id = item.get("id", 0)
            model = (item.get("model") or "").strip()
            name = (item.get("name") or "").strip()
            cid = item.get("category")

            if not model or not name or cid is None:
                continue

            category_obj = cat_map.get(cid)
            if not category_obj:
                continue

            product, _ = Product.objects.get_or_create(
                model=model,
                defaults={"name": name, "category": category_obj},
            )

            p_updated = False
            if product.name != name:
                product.name = name
                p_updated = True
            if product.category_id != category_obj.id:
                product.category = category_obj
                p_updated = True
            if p_updated:
                product.save(update_fields=["name", "category_id"])

            product_info = ProductInfo.objects.create(
                product=product,
                shop=shop,
                external_id=external_id,
                quantity=item.get("quantity", 0),
                price=item.get("price", 0),
                price_rrc=item.get("price_rrc", 0),
            )

            params = item.get("parameters") or {}
            if isinstance(params, dict):
                for pname, pvalue in params.items():
                    param_obj, _ = Parameter.objects.get_or_create(name=str(pname))
                    ProductParameter.objects.create(
                        product_info=product_info,
                        parameter=param_obj,
                        value=str(pvalue),
                    )

    return {"success": True, "shop_id": shop_id}