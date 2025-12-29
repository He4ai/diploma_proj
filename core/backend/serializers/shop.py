from rest_framework import serializers
from backend.models import ShopOrder, OrderItem, Shop, Category, ProductInfo, Product, Parameter, ProductParameter
from django.db import transaction

# Сериализатор для позиций заказа
class ShopOrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product_info.product_id", read_only=True)
    product_name = serializers.CharField(source="product_info.product.name", read_only=True)
    product_model = serializers.CharField(source="product_info.product.model", read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_model",
            "quantity",
            "price_at_purchase",
        )


# Сериализатор на выдачу данных о заказе для продавца
class ShopOrderSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="order.id", read_only=True)
    date = serializers.DateTimeField(source="order.date", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)

    shipping_country = serializers.CharField(source="order.shipping_country", read_only=True)
    shipping_city = serializers.CharField(source="order.shipping_city", read_only=True)
    shipping_street = serializers.CharField(source="order.shipping_street", read_only=True)
    shipping_house = serializers.CharField(source="order.shipping_house", read_only=True)
    shipping_apartment = serializers.CharField(source="order.shipping_apartment", read_only=True)

    items = ShopOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShopOrder
        fields = (
            "id",
            "order_id",
            "date",
            "order_status",
            "status",
            "shipping_country",
            "shipping_city",
            "shipping_street",
            "shipping_house",
            "shipping_apartment",
            "items",
        )


# Смена статуса заказа
class ChangeShopOrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ShopOrder.Status.choices)

    # Четкий порядок статусов
    STATUS_FLOW = [
        ShopOrder.Status.PROCESSING,
        ShopOrder.Status.CONFIRMED,
        ShopOrder.Status.ASSEMBLED,
        ShopOrder.Status.SENT,
        ShopOrder.Status.DELIVERED,
    ]

    FORBIDDEN_TARGETS = {ShopOrder.Status.BASKET}

    def validate_status(self, new_status: str) -> str:
        if new_status in self.FORBIDDEN_TARGETS:
            raise serializers.ValidationError("Нельзя менять статус подзаказа на 'basket'.")

        shop_order = self.context.get("shop_order")
        if not shop_order:
            raise serializers.ValidationError("Не передан текущий подзаказ (shop_order) для проверки перехода.")

        current_status = shop_order.status
        # Продавец не может менять статус заказа, если его статус корзина
        if current_status == ShopOrder.Status.BASKET:
            raise serializers.ValidationError("Подзаказ в статусе 'basket' менять нельзя.")
        # Нельзя поменять статус заказа, если он отменен или доставлен
        if current_status in {ShopOrder.Status.DELIVERED, ShopOrder.Status.CANCELED}:
            raise serializers.ValidationError("Финальный статус менять нельзя.")

        if new_status == ShopOrder.Status.CANCELED:
            # отменять можно из любого статуса, кроме basket и финальных
            return new_status

        flow = self.STATUS_FLOW

        if current_status not in flow or new_status not in flow:
            raise serializers.ValidationError("Некорректный статус для перехода.")


        cur_i = flow.index(current_status)
        new_i = flow.index(new_status)

        # Статус можно менять исключительно на следующий по порядку вперед (перескакивать через 1 или уходить назад нельзя)
        if new_i != cur_i + 1:
            allowed = flow[cur_i + 1] if cur_i + 1 < len(flow) else None
            raise serializers.ValidationError(
                f"Нельзя перейти из '{current_status}' в '{new_status}'. "
                f"Разрешён только следующий статус: '{allowed}'."
            )

        return new_status


class ShopStateSerializer(serializers.Serializer):
    state = serializers.BooleanField()


class ChangeShopInfoSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    url = serializers.URLField(required=False)
    state = serializers.BooleanField(required=False)

    add_categories = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    remove_categories = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Shop
        fields = ("name", "url", "state", "add_categories", "remove_categories")

    def validate(self, data):
        shop = self.instance
        if not shop:
            raise serializers.ValidationError("Shop not found")

        changed_fields = {}

        add_list = [s.strip() for s in data.get("add_categories", []) if s and s.strip()] # Все добавленные категории
        remove_list = [s.strip() for s in data.get("remove_categories", []) if s and s.strip()] # Все удаленные категории

        # Проверка на случай, если одна и та же категория удаляется и создается
        if add_list and remove_list:
            conflict = set(map(str.casefold, add_list)) & set(map(str.casefold, remove_list))
            if conflict:
                raise serializers.ValidationError({
                    "categories": f"Категории не могут одновременно добавляться и удаляться: {sorted(conflict)}"
                })

        current_names = list(shop.categories.values_list("name", flat=True))
        current_cf = {n.casefold() for n in current_names}
        # Проверка на то, есть ли вообще какие-либо добавления категорий, если есть хотя бы одно - выходим из цикла
        if add_list:
            for name in add_list:
                if name.casefold() not in current_cf:
                    changed_fields["_add_categories"] = add_list
                    break
        # То же самое с удалением категорий
        if remove_list:
            for name in remove_list:
                if name.casefold() in current_cf:
                    changed_fields["_remove_categories"] = remove_list
                    break
        # Дальше проверки на то, есть ли какие-либо изменения
        if "name" in data and data["name"] != shop.name:
            changed_fields["name"] = data["name"]

        if "url" in data and data["url"] != shop.url:
            changed_fields["url"] = data["url"]

        if "state" in data and data["state"] != shop.state:
            state_ser = ShopStateSerializer(data={"state": data["state"]}, context={"shop": shop})
            state_ser.is_valid(raise_exception=True)
            changed_fields["state"] = state_ser.validated_data["state"]
        # Чтобы здесь финально посмотреть, были ли изменения вообще
        if not changed_fields:
            raise serializers.ValidationError("Нет изменений.")

        return changed_fields

    @transaction.atomic
    def update(self, instance, validated_data):
        add_list = validated_data.pop("_add_categories", [])
        remove_list = validated_data.pop("_remove_categories", [])
        # Добавление обычных полей (не категорий)
        if validated_data:
            for k, v in validated_data.items():
                setattr(instance, k, v)
            instance.save(update_fields=list(validated_data.keys()))

        current_names = set(
            instance.categories.values_list("name", flat=True)
        )
        current_cf = set(n.casefold() for n in current_names)

        # Удаление категорий
        if remove_list:
            remove_cf = set(x.casefold() for x in remove_list)
            to_remove = Category.objects.filter(name__in=current_names).filter(
                name__in=[n for n in current_names if n.casefold() in remove_cf]
            )
            if to_remove.exists():
                instance.categories.remove(*to_remove)
        # Добавление категорий
        if add_list:
            to_add_names = [n for n in add_list if n.casefold() not in current_cf]

            cats_to_add = []
            for name in to_add_names:
                cat, _ = Category.objects.get_or_create(name=name)
                cats_to_add.append(cat)

            if cats_to_add:
                instance.categories.add(*cats_to_add)

        return instance

# Для вывода информации о магазине
class ShopFullSerializer(serializers.ModelSerializer):
    categories = serializers.SlugRelatedField(
        many=True,
        read_only=True,
        slug_field="name"
    )

    class Meta:
        model = Shop
        fields = ("id", "name", "url", "state", "categories")

# Создание карточки товара
class ProductInfoCreateSerializer(serializers.ModelSerializer):
    model = serializers.CharField(required=True)
    external_id = serializers.IntegerField(required=True)
    quantity = serializers.IntegerField(required=True, min_value=0)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    price_rrc = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

    name = serializers.CharField(required=False)
    category = serializers.IntegerField(required=False)

    # параметры как dict: {"Цвет": "красный", "Память": "256"}
    parameters = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        write_only=True,
    )

    class Meta:
        model = ProductInfo
        fields = ("model", "external_id", "quantity", "price", "price_rrc", "name", "category", "parameters")

    def validate(self, attrs):
        shop = self.context["shop"]
        model = attrs["model"]

        product = Product.objects.filter(model=model).first()

        if not product:
            if not attrs.get("name"):
                raise serializers.ValidationError({"name": "Обязательное поле для нового продукта"})
            if not attrs.get("category"):
                raise serializers.ValidationError({"category": "Обязательное поле для нового продукта"})
            if not shop.categories.filter(id=attrs["category"]).exists():
                raise serializers.ValidationError({"category": "Категория не принадлежит магазину"})

        if ProductInfo.objects.filter(shop=shop, external_id=attrs["external_id"]).exists():
            raise serializers.ValidationError({"external_id": "У этого магазина уже есть такой external_id"})

        params = attrs.get("parameters")
        if params is not None and not isinstance(params, dict):
            raise serializers.ValidationError({"parameters": "Должен быть объектом вида {name: value}."})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        shop = self.context["shop"]
        params = validated_data.pop("parameters", None)

        model = validated_data["model"]
        product = Product.objects.filter(model=model).first()
        if not product:
            product = Product.objects.create(
                model=model,
                name=validated_data.pop("name"),
                category_id=validated_data.pop("category"),
            )
        else:
            # если product существует — name/category из validated_data просто игнорим
            validated_data.pop("name", None)
            validated_data.pop("category", None)

        product_info = ProductInfo.objects.create(
            product=product,
            shop=shop,
            external_id=validated_data["external_id"],
            quantity=validated_data["quantity"],
            price=validated_data["price"],
            price_rrc=validated_data["price_rrc"],
        )

        if params:
            for pname, pvalue in params.items():
                pname = str(pname).strip()
                if not pname:
                    continue
                param_obj, _ = Parameter.objects.get_or_create(name=pname)
                ProductParameter.objects.create(
                    product_info=product_info,
                    parameter=param_obj,
                    value=str(pvalue),
                )

        return product_info

class ProductInfoUpdateSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(required=False, min_value=0)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    price_rrc = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)

    # установить параметры
    parameters = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        write_only=True,
    )
    # удалить параметры по имени
    remove_parameters = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = ProductInfo
        fields = ("quantity", "price", "price_rrc", "parameters", "remove_parameters")

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Нет изменений.")

        params = attrs.get("parameters")
        if params is not None and not isinstance(params, dict):
            raise serializers.ValidationError({"parameters": "Должен быть объектом вида {name: value}."})

        remove_list = attrs.get("remove_parameters")
        if remove_list is not None:
            cleaned = []
            for x in remove_list:
                x = (x or "").strip()
                if x:
                    cleaned.append(x)
            attrs["remove_parameters"] = cleaned

        # конфликт: одно и то же имя в parameters и remove_parameters
        if params is not None and remove_list:
            p_cf = {str(k).casefold() for k in params.keys()}
            r_cf = {str(k).casefold() for k in attrs["remove_parameters"]}
            conflict = sorted(p_cf & r_cf)
            if conflict:
                raise serializers.ValidationError(
                    {"parameters": f"Нельзя одновременно обновлять и удалять: {conflict}"}
                )

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        params = validated_data.pop("parameters", None)
        remove_list = validated_data.pop("remove_parameters", [])

        # обновить поля ProductInfo
        if validated_data:
            for k, v in validated_data.items():
                setattr(instance, k, v)
            instance.save(update_fields=list(validated_data.keys()))

        # удалить параметры
        if remove_list:
            # найдём parameter ids по именам (case-insensitive)
            current = ProductParameter.objects.filter(product_info=instance).select_related("parameter")
            to_delete_ids = [
                pp.id for pp in current
                if pp.parameter.name.casefold() in {x.casefold() for x in remove_list}
            ]
            if to_delete_ids:
                ProductParameter.objects.filter(id__in=to_delete_ids).delete()

        # установить параметры
        if params:
            # текущие параметры оффера: name(casefold) -> ProductParameter
            existing = {
                pp.parameter.name.casefold(): pp
                for pp in ProductParameter.objects.filter(product_info=instance).select_related("parameter")
            }

            for pname, pvalue in params.items():
                pname = str(pname).strip()
                if not pname:
                    continue

                key = pname.casefold()
                value_str = str(pvalue)

                if key in existing:
                    pp = existing[key]
                    if pp.value != value_str:
                        pp.value = value_str
                        pp.save(update_fields=["value"])
                else:
                    param_obj, _ = Parameter.objects.get_or_create(name=pname)
                    ProductParameter.objects.create(
                        product_info=instance,
                        parameter=param_obj,
                        value=value_str,
                    )

        return instance

class ProductParameterReadSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="parameter.name", read_only=True)

    class Meta:
        model = ProductParameter
        fields = ("name", "value")


class ProductInfoReadSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_model = serializers.CharField(source="product.model", read_only=True)
    category_id = serializers.IntegerField(source="product.category.id", read_only=True)
    category_name = serializers.CharField(source="product.category.name", read_only=True)

    parameters = ProductParameterReadSerializer(many=True, read_only=True)

    class Meta:
        model = ProductInfo
        fields = (
            "id",
            "external_id",
            "quantity",
            "price",
            "price_rrc",
            "product_id",
            "product_name",
            "product_model",
            "category_id",
            "category_name",
            "parameters",
        )