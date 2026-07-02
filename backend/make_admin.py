"""Create or promote an admin user (bootstrap the first admin).

Registration is invite-only and only admins can send invites, so the first
admin must be created out-of-band:

    python make_admin.py <username>            # prompts for a password if creating
    python make_admin.py <username> <password>

If the user exists, they're promoted to admin; otherwise a new admin user is
created with the given password.
"""
import asyncio
import getpass
import sys

import bcrypt
from sqlalchemy import select

from db import AsyncSessionLocal, User


async def main(username: str, password: str | None) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.username == username))
        if user is not None:
            user.is_admin = True
            await session.commit()
            print(f"'{username}' is now an admin.")
            return

        if not password:
            password = getpass.getpass(f"New password for '{username}': ")
        if len(password) < 8:
            print("Password must be at least 8 characters.")
            sys.exit(1)

        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        session.add(User(username=username, password_hash=pw_hash, is_admin=True))
        await session.commit()
        print(f"Created admin user '{username}'.")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: python make_admin.py <username> [password]")
        sys.exit(2)
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None))
