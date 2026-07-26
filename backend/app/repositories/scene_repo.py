from app.repositories.base import BaseRepository
from app.models.scene import Scene, Panel, Shot
from app.models.bubble import Bubble


class SceneRepository(BaseRepository[Scene]):
    def __init__(self, session):
        super().__init__(Scene, session)


class PanelRepository(BaseRepository[Panel]):
    def __init__(self, session):
        super().__init__(Panel, session)


class ShotRepository(BaseRepository[Shot]):
    def __init__(self, session):
        super().__init__(Shot, session)


class BubbleRepository(BaseRepository[Bubble]):
    def __init__(self, session):
        super().__init__(Bubble, session)
