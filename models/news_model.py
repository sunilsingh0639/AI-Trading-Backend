from pydantic import BaseModel

class NewsModel(BaseModel):

    title: str

    description: str | None = None

    source: str

    url: str

    published: str | None = None

    sentiment: str | None = None