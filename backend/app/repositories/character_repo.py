from uuid import UUID

from sqlalchemy import or_, select

from app.repositories.base import BaseRepository
from app.models.character import Character, CharacterRelation, CharacterOutfit, CharacterReferenceImage


class CharacterRepository(BaseRepository[Character]):
    def __init__(self, session):
        super().__init__(Character, session)


class CharacterRelationRepository(BaseRepository[CharacterRelation]):
    def __init__(self, session):
        super().__init__(CharacterRelation, session)

    async def list_by_character(self, character_id: UUID) -> list:
        result = await self.session.execute(
            select(CharacterRelation).where(
                or_(
                    CharacterRelation.character_a_id == character_id,
                    CharacterRelation.character_b_id == character_id,
                )
            )
        )
        return list(result.scalars().all())


class CharacterOutfitRepository(BaseRepository[CharacterOutfit]):
    def __init__(self, session):
        super().__init__(CharacterOutfit, session)


class CharacterReferenceImageRepository(BaseRepository[CharacterReferenceImage]):
    def __init__(self, session):
        super().__init__(CharacterReferenceImage, session)
