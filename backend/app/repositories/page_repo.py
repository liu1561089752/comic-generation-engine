from app.repositories.base import BaseRepository
from app.models.page import Page


class PageRepository(BaseRepository[Page]):
    def __init__(self, session):
        super().__init__(Page, session)
