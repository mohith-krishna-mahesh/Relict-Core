from pydantic import BaseModel


class Species(BaseModel):
    name: str
    taxonomy_id: str


class Gene(BaseModel):
    symbol: str
    name: str