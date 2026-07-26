from app.repositories.base import BaseRepository
from app.models.prompt import Prompt


class PromptRepository(BaseRepository[Prompt]):
    def __init__(self, session):
        super().__init__(Prompt, session)
