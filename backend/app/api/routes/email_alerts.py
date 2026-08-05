from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_superuser
from app.db.models import User
from app.schemas.email_alert import (
    EmailActionOut,
    EmailDeliveryDetailOut,
    EmailDeliveryListPage,
    EmailSettingsOut,
    EmailSettingsUpdate,
    EmailTemplatePreviewIn,
    EmailTemplatePreviewOut,
    TestEmailIn,
)
from app.services.auth import user_audit_details
from app.services.email_alerts import (
    create_test_email_delivery,
    get_email_delivery_detail,
    get_email_settings_out,
    list_email_deliveries,
    preview_email_templates,
    resend_failed_email_delivery,
    update_email_settings,
)


router = APIRouter()


@router.get("/email-settings", response_model=EmailSettingsOut)
async def get_email_alert_settings(
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> EmailSettingsOut:
    return get_email_settings_out(db)


@router.patch("/email-settings", response_model=EmailSettingsOut)
async def patch_email_alert_settings(
    payload: EmailSettingsUpdate,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> EmailSettingsOut:
    try:
        return update_email_settings(
            db,
            payload,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/email-settings/preview", response_model=EmailTemplatePreviewOut)
async def preview_email_alert_template(
    payload: EmailTemplatePreviewIn,
    _: User = Depends(require_superuser),
) -> EmailTemplatePreviewOut:
    try:
        return preview_email_templates(
            subject_template=payload.subject_template,
            text_body_template=payload.text_body_template,
            html_body_template=payload.html_body_template,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/email-settings/test", response_model=EmailActionOut)
async def send_test_email(
    payload: TestEmailIn,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> EmailActionOut:
    try:
        return create_test_email_delivery(
            db,
            recipient_email=payload.recipient_email,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/email-deliveries", response_model=EmailDeliveryListPage)
async def get_email_deliveries(
    status: str | None = Query(
        default=None,
        pattern="^(queued|sending|retry_scheduled|sent|failed|skipped)$",
    ),
    trigger_type: str | None = Query(
        default=None, pattern="^(automatic|manual|test|manual_retry)$"
    ),
    recipient_email: str | None = Query(default=None, max_length=320),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> EmailDeliveryListPage:
    return list_email_deliveries(
        db,
        status=status,
        trigger_type=trigger_type,
        recipient_email=recipient_email,
        offset=offset,
        limit=limit,
    )


@router.get("/email-deliveries/{delivery_id}", response_model=EmailDeliveryDetailOut)
async def get_email_delivery(
    delivery_id: str,
    _: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> EmailDeliveryDetailOut:
    result = get_email_delivery_detail(db, delivery_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Email delivery not found")
    return result


@router.post("/email-deliveries/{delivery_id}/resend", response_model=EmailActionOut)
async def resend_email_delivery(
    delivery_id: str,
    current_user: User = Depends(require_superuser),
    db: Session = Depends(get_db),
) -> EmailActionOut:
    try:
        return resend_failed_email_delivery(
            db,
            delivery_id,
            actor_id=current_user.id,
            actor_details=user_audit_details(current_user),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
