# from rest_framework import serializers
# from api.api.masters.customer_masters.customercreation import CustomerCreation


# class CustomerNestedSerializer(serializers.ModelSerializer):

#     city_name = serializers.CharField(source="city.name", read_only=True)
#     zone_name = serializers.CharField(source="zone.name", read_only=True)
#     district_name = serializers.CharField(source="district.name", read_only=True)
#     state_name = serializers.CharField(source="state.name", read_only=True)
#     country_name = serializers.CharField(source="country.name", read_only=True)
#     ward_name = serializers.CharField(source="ward.name", read_only=True)
#     property_name = serializers.CharField(source="property.property_name", read_only=True)
#     sub_property_name = serializers.CharField(source="sub_property.sub_property_name", read_only=True)

#     class Meta:
#         model = CustomerCreation
#         fields = [
#             "id",
#             "customer_name",
#             "contact_no",
#             "building_no",
#             "street",
#             "area",
#             "pincode",
#             "latitude",
#             "longitude",
#             "id_proof_type",
#             "id_no",
#             "city_name",
#             "zone_name",
#             "district_name",
#             "state_name",
#             "country_name",
#             "ward_name",
#             "property_name",
#             "sub_property_name",
#         ]
