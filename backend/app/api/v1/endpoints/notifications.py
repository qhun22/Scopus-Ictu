"""Current-user persistent notification endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.core.exceptions import APIError
from app.models.governance import User, UserNotification
from app.schemas.notification import NotificationReadResponse, NotificationResponse


router = APIRouter()
CurrentUser = Annotated[User, Depends(get_current_user)]
DatabaseSession = Annotated[Session, Depends(get_session)]


def _notification_response(notification: UserNotification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        metadata=notification.notification_metadata or {},
        is_read=notification.is_read,
        created_at=notification.created_at,
        read_at=notification.read_at,
    )


@router.get(
    "/unread",
    response_model=list[NotificationResponse],
    summary="List the current user's unread notifications",
)
def list_unread_notifications(
    current_user: CurrentUser,
    db: DatabaseSession,
) -> list[NotificationResponse]:
    try:
        notifications = (
            db.query(UserNotification)
            .filter(
                UserNotification.user_id == current_user.id,
                UserNotification.is_read.is_(False),
            )
            .order_by(UserNotification.created_at.asc(), UserNotification.id.asc())
            .all()
        )
        return [_notification_response(notification) for notification in notifications]
    except SQLAlchemyError as exc:
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tải thông báo.",
            code="DATABASE_UNAVAILABLE",
        ) from exc


@router.post(
    "/{notification_id}/read",
    response_model=NotificationReadResponse,
    summary="Mark one owned notification as read",
)
def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> NotificationReadResponse:
    try:
        notification = (
            db.query(UserNotification)
            .filter(
                UserNotification.id == notification_id,
                UserNotification.user_id == current_user.id,
            )
            .first()
        )
        if notification is None:
            raise APIError(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy thông báo.",
                code="NOTIFICATION_NOT_FOUND",
            )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(notification)
        return NotificationReadResponse(
            id=notification.id,
            is_read=True,
            read_at=notification.read_at,
        )
    except APIError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise APIError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể đánh dấu thông báo đã đọc.",
            code="DATABASE_UNAVAILABLE",
        ) from exc
