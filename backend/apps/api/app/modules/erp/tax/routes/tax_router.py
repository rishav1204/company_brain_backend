from fastapi import APIRouter

from app.modules.erp.tax.routes import compliance_routes, e_invoice_routes, eway_bill_routes, filing_routes, gst_routes, reconciliation_routes, tds_routes

erp_gst_router = APIRouter(prefix="/gst", tags=["erp-gst"])
erp_gst_router.include_router(gst_routes.router)
erp_gst_router.include_router(filing_routes.router)
erp_gst_router.include_router(reconciliation_routes.router)
erp_gst_router.include_router(e_invoice_routes.router)
erp_gst_router.include_router(eway_bill_routes.router)

erp_tds_router = APIRouter(prefix="/tds", tags=["erp-tds"])
erp_tds_router.include_router(tds_routes.router)

erp_compliance_router = APIRouter(prefix="/compliance", tags=["erp-compliance"])
erp_compliance_router.include_router(compliance_routes.router)
