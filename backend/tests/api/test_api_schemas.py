from compliance.api import schemas as api_schemas
from compliance.services import schemas as service_schemas


class TestApiSchemas:
    def test_api_schemas_are_distinct_from_service_schemas(self) -> None:
        assert api_schemas.ClientCreate is not service_schemas.ClientCreate
        assert api_schemas.ClientOut is not service_schemas.ClientOut
        assert issubclass(api_schemas.ClientCreate, service_schemas.ClientCreate)
        assert issubclass(api_schemas.ClientOut, service_schemas.ClientOut)

    def test_api_create_schema_remains_service_compatible(self) -> None:
        client = api_schemas.ClientCreate(
            nif="A1234567B",
            company_name="Example Farm",
            contact_name="Alice Inspector",
            email="alice@example.com",
            telephone=555123456,
        )

        assert isinstance(client, service_schemas.ClientCreate)
        assert service_schemas.ClientCreate.model_validate(client) == client
