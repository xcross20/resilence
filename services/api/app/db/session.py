from fastapi import Request
from sqlalchemy.orm import Session


def session_for(request: Request) -> Session:
    return Session(request.app.state.engine)
