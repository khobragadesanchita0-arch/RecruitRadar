import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import engine, Base, AsyncSessionLocal
from app.db.models import User, Workspace, WorkspaceMember
from app.core.security import hash_password

async def init_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Check if default workspace and admin user exist
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "recruiter@recruitradar.io"))
        user = result.scalar_one_or_none()
        if not user:
            # Create default workspace
            workspace = Workspace(
                name="Default Workspace",
                retention_days=180,
                blind_mode_default=True
            )
            session.add(workspace)
            await session.flush()
            
            # Create default recruiter user
            user = User(
                email="recruiter@recruitradar.io",
                name="Demo Recruiter",
                password_hash=hash_password("Password123!"),
                status="active"
            )
            session.add(user)
            await session.flush()
            
            # Link membership as owner
            member = WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner"
            )
            session.add(member)
            await session.commit()

if __name__ == "__main__":
    asyncio.run(init_database())
