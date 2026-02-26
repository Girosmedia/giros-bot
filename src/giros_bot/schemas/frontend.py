"""
PostFrontmatter — Mirror de PostFrontmatter interface en el frontend Next.js.
El Writer_Agent debe generar MDX que cumpla estrictamente con este schema.
"""


from pydantic import BaseModel, Field

from .state import FrontendCategory


class PostFrontmatter(BaseModel):
    """
    Representa el frontmatter YAML de un archivo .mdx.
    Debe coincidir con la interface PostFrontmatter de types.ts en el frontend.
    """

    title:      str             = Field(..., min_length=10, max_length=100)
    description: str            = Field(..., min_length=100, max_length=165, description="SEO description 150-160 chars")
    date:       str             = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    category:   FrontendCategory
    tags:       list[str]       = Field(..., min_length=3, max_length=7)
    image:      str | None   = Field(default=None, description="/blog/{slug}.jpg")
    imageAlt:   str | None   = None
    author:     str             = "Equipo Giros Media"
    authorRole: str | None   = "Especialistas en Presencia Digital"

    def to_yaml_frontmatter(self) -> str:
        """Serializa el frontmatter en formato YAML para el archivo .mdx."""
        import yaml

        data = self.model_dump(exclude_none=False)
        # Asegurar que category sea el valor string, no el Enum
        data["category"] = self.category.value
        # Eliminar campos None opcionales para el YAML
        data = {k: v for k, v in data.items() if v is not None}
        return f"---\n{yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)}---\n"
