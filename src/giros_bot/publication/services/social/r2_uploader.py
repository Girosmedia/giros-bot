"""
Servicio de upload de imágenes a Cloudflare R2.

Responsabilidades:
  - Subir imágenes JPEG (con watermark) al bucket R2 bajo el prefijo social/
  - Generar presigned URLs con TTL de 1 hora (suficiente para que Meta las descargue)
  - Limpieza lazy de imágenes con más de 7 días bajo el prefijo social/

El cliente boto3 se crea una sola vez (singleton) y se reutiliza.
Todas las operaciones son síncronas y deben invocarse con asyncio.to_thread()
desde el publisher_node para no bloquear el event loop.
"""

import logging
from datetime import datetime, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from ....config import settings

logger = logging.getLogger(__name__)

# Prefijo dentro del bucket donde se almacenan las imágenes de RRSS
_SOCIAL_PREFIX = "social/"

# TTL de la presigned URL en segundos (1 hora es más que suficiente para que
# Meta descargue la imagen al procesar la publicación)
_PRESIGNED_TTL = 3600

# Imágenes con más de estos días bajo social/ se eliminarán en la limpieza lazy
_CLEANUP_DAYS = 7


def _get_client():
    """Crea y retorna un cliente boto3 S3 apuntando al endpoint de Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_image_to_r2(image_bytes: bytes, filename: str) -> str:
    """
    Sube una imagen JPEG al bucket R2 bajo el prefijo social/ y retorna
    una presigned URL válida por _PRESIGNED_TTL segundos.

    Args:
        image_bytes: Bytes crudos de la imagen JPEG.
        filename:    Nombre del archivo, ej: "tienda-online-sin-stock.jpg"

    Returns:
        Presigned URL pública temporal (string).

    Raises:
        ClientError: Si falla la subida o la generación de la URL.
    """
    if not all(
        [
            settings.r2_endpoint_url,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
        ]
    ):
        raise ValueError(
            "Credenciales de R2 no configuradas (R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME)."
        )

    key = f"{_SOCIAL_PREFIX}{filename}"
    client = _get_client()

    logger.info("R2: subiendo imagen → s3://%s/%s", settings.r2_bucket_name, key)
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )

    presigned_url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=_PRESIGNED_TTL,
    )
    logger.info("R2: presigned URL generada (TTL %ds) → %s", _PRESIGNED_TTL, presigned_url)
    return presigned_url


def cleanup_old_social_images(days: int = _CLEANUP_DAYS) -> int:
    """
    Elimina objetos bajo el prefijo social/ con más de `days` días de antigüedad.
    Se invoca de forma lazy (en background) cada vez que se sube una imagen nueva.

    Args:
        days: Umbral de antigüedad en días para considerar una imagen como candidata
              a eliminación. Por defecto 7 días.

    Returns:
        Número de objetos eliminados.
    """
    if not all(
        [
            settings.r2_endpoint_url,
            settings.r2_access_key_id,
            settings.r2_secret_access_key,
            settings.r2_bucket_name,
        ]
    ):
        logger.warning("R2 cleanup: credenciales no configuradas, saltando limpieza.")
        return 0

    client = _get_client()
    now = datetime.now(tz=timezone.utc)
    deleted_count = 0

    try:
        paginator = client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=settings.r2_bucket_name, Prefix=_SOCIAL_PREFIX)

        to_delete = []
        for page in pages:
            for obj in page.get("Contents", []):
                age_days = (now - obj["LastModified"]).days
                if age_days >= days:
                    to_delete.append({"Key": obj["Key"]})
                    logger.debug("R2 cleanup: candidato → %s (%d días)", obj["Key"], age_days)

        if not to_delete:
            logger.info(
                "R2 cleanup: no hay imágenes antiguas para eliminar (umbral: %d días).", days
            )
            return 0

        # La API de delete_objects acepta hasta 1000 keys por llamada
        for i in range(0, len(to_delete), 1000):
            batch = to_delete[i : i + 1000]
            client.delete_objects(
                Bucket=settings.r2_bucket_name,
                Delete={"Objects": batch, "Quiet": True},
            )
            deleted_count += len(batch)

        logger.info("R2 cleanup: %d imagen(es) eliminada(s) (>%d días).", deleted_count, days)

    except ClientError as e:
        logger.error("R2 cleanup: error durante la limpieza → %s", e)

    return deleted_count
