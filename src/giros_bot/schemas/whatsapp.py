"""Modelos Pydantic v2 para el payload webhook de Meta (WhatsApp Business).

Referencia: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
"""


from pydantic import BaseModel, ConfigDict, Field, model_validator


class WhatsAppTextContent(BaseModel):
    body: str


class WhatsAppMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    timestamp: str
    type: str
    # "from" es palabra reservada en Python → alias
    from_: str = Field(..., alias="from")
    text: WhatsAppTextContent | None = None


class WhatsAppProfile(BaseModel):
    name: str


class WhatsAppContact(BaseModel):
    profile: WhatsAppProfile
    wa_id: str


class WhatsAppValue(BaseModel):
    messaging_product: str
    contacts: list[WhatsAppContact] | None = None
    messages: list[WhatsAppMessage] | None = None


class WhatsAppChange(BaseModel):
    value: WhatsAppValue
    field: str


class WhatsAppEntry(BaseModel):
    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhookPayload(BaseModel):
    """Payload completo enviado por Meta al webhook."""

    object: str
    entry: list[WhatsAppEntry]

    @model_validator(mode="after")
    def validate_object_type(self) -> "WhatsAppWebhookPayload":
        if self.object != "whatsapp_business_account":
            raise ValueError(
                f"Payload no pertenece a WhatsApp Business (object={self.object!r})"
            )
        return self


class OutboundMessage(BaseModel):
    """Modelo para preparar el payload de envío a Meta Graph API."""

    recipient_phone: str
    text: str
    preview_url: bool = False
