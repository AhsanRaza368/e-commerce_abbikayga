
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from services.rate_limiter import limiter
from fastapi import Request, Response
from database import get_db
from models import AdminUser, AuditLog, Listing, Report
from routes.customers import get_current_customer
from routes.auth import get_current_admin
from schemas import (
    ReportCreate,
    ReportPublic,
    ReportReceipt,
    ReportStatusUpdate,
)


router = APIRouter(tags=["Reports"])


@router.post(
    "/listings/{listing_id}/reports",
    response_model=ReportReceipt,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_customer)],
)
@limiter.limit("5/hour")
def create_listing_report(
    listing_id: int,
    report_data: ReportCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Allow an authenticated customer to report a public advertisement."""

    listing = db.get(Listing, listing_id)

    # Do not accept reports against advertisements that are not public.
    if listing is None or listing.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )

    report = Report(
        listing_id=listing.id,
        reason=report_data.reason,
        details=report_data.details,
        reporter_contact=report_data.reporter_contact,
        status="open",
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    # Do not return the reporter's contact details publicly.
    return report


@router.get(
    "/admin/reports/",
    response_model=list[ReportPublic],
)
def get_reports(
    report_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(open|reviewed|resolved|dismissed)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List reports for authenticated administrators."""

    statement = select(Report).options(joinedload(Report.listing))

    if report_status:
        statement = statement.where(Report.status == report_status)

    statement = (
        statement
        .order_by(Report.created_at.desc(), Report.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return db.scalars(statement).all()


@router.patch(
    "/admin/reports/{report_id}/status",
    response_model=ReportPublic,
)
def update_report_status(
    report_id: int,
    status_data: ReportStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Update a report and record the action in the audit log."""

    report = db.get(Report, report_id)

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    previous_status = report.status
    new_status = status_data.status

    report.status = new_status

    audit_entry = AuditLog(
        admin_id=current_admin.id,
        action="report_status_updated",
        entity_type="report",
        entity_id=report.id,
        details={
            "previous_status": previous_status,
            "new_status": new_status,
            "listing_id": report.listing_id,
        },
    )

    try:
        db.add(audit_entry)
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise

    return report
