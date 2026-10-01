"""
Seed taxonomy database tables with canonical skills and aliases.
Reads from backend/app/taxonomy/seed/skills.json and aliases.json.
"""
import asyncio
import json
from pathlib import Path
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Skill, SkillAlias

BASE_DIR = Path(__file__).resolve().parent.parent / "backend" / "app" / "taxonomy" / "seed"


async def seed_taxonomy():
    skills_file = BASE_DIR / "skills.json"
    aliases_file = BASE_DIR / "aliases.json"

    if not skills_file.exists():
        print(f"Error: {skills_file} not found.")
        return

    with open(skills_file, "r", encoding="utf-8") as f:
        skills_data = json.load(f)

    aliases_data = {}
    if aliases_file.exists():
        with open(aliases_file, "r", encoding="utf-8") as f:
            aliases_data = json.load(f)

    async with AsyncSessionLocal() as session:
        print(f"Seeding {len(skills_data)} canonical skills...")
        skill_id_map = {}

        for item in skills_data:
            canonical_name = item["canonical_name"]
            stmt = select(Skill).where(Skill.canonical_name == canonical_name)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()

            if not existing:
                skill = Skill(
                    id=item.get("id"),
                    canonical_name=canonical_name,
                    category=item.get("category", "General"),
                    release_year=item.get("release_year"),
                )
                session.add(skill)
                skill_id_map[canonical_name] = skill.id
            else:
                skill_id_map[canonical_name] = existing.id

        await session.commit()

        # Seed aliases
        print(f"Seeding aliases...")
        alias_count = 0
        for alias_name, canonical_target in aliases_data.items():
            canonical_skill_id = skill_id_map.get(canonical_target)
            if not canonical_skill_id:
                # Query DB if not in map
                stmt = select(Skill).where(Skill.canonical_name == canonical_target)
                res = await session.execute(stmt)
                db_skill = res.scalar_one_or_none()
                if db_skill:
                    canonical_skill_id = db_skill.id

            if canonical_skill_id:
                stmt = select(SkillAlias).where(
                    SkillAlias.alias == alias_name,
                    SkillAlias.skill_id == canonical_skill_id,
                )
                res = await session.execute(stmt)
                if not res.scalar_one_or_none():
                    session.add(SkillAlias(skill_id=canonical_skill_id, alias=alias_name))
                    alias_count += 1

        await session.commit()
        print(f"Taxonomy seeding complete. Seeded {len(skills_data)} skills and {alias_count} new aliases.")


if __name__ == "__main__":
    asyncio.run(seed_taxonomy())
