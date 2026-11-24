"""Authenticated, read-only source handoff for the filling workspace."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import auth
from ..services.documents import document_root
from ..services.notice_source_snapshot import SourceSnapshotError, read_source_snapshot
from .common import data


class NoStoreRoute(APIRoute):
    """Cover dependency and parameter failures without changing other routes."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def no_store(request: Request):
            try:
                response = await handler(request)
            except StarletteHTTPException as exc:
                response = await http_exception_handler(request, exc)
            except RequestValidationError as exc:
                response = await request_validation_exception_handler(request, exc)
            response.headers['Cache-Control'] = 'no-store'
            return response

        return no_store


router = APIRouter(route_class=NoStoreRoute)


@router.get('/api/v1/import-batches/{batch_id}/form-context')
def get_form_context(batch_id: str, expected_revision: int = Query(..., ge=0),
                     user=Depends(auth.current_user)):
    """Read one snapshot; revision alone does not identify the source set."""
    connection = auth.conn()
    try:
        try:
            result = read_source_snapshot(connection, user['id'], batch_id,
                                          expected_revision, original_root=document_root())
        except SourceSnapshotError as exc:
            status = 404 if exc.code == 'BATCH_NOT_FOUND' else 409
            raise HTTPException(status, {'code': exc.code}) from exc
    finally:
        if auth.DB != ':memory:':
            connection.close()
    return data({'schema_version': 1, **result})
