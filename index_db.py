import asyncio
import models_final as models
import database

if __name__ == "__main__":
    async def startup():
        print("Starting up... Dropping and recreating database tables for development.")
        async with database.engine.begin() as conn:
            await conn.run_sync(models.Base.metadata.drop_all)
            await conn.run_sync(models.Base.metadata.create_all)
        print("Database tables created.")

    asyncio.run(startup())