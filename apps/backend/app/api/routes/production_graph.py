"""Phase 11 — 生产依赖图接口。"""

from fastapi import APIRouter, Request

from app.core.errors import AppError
from app.schemas.production_graph import (
    AffectedNodesOut,
    ProductionEdgeCreate,
    ProductionEdgeOut,
)
from app.services.production_graph import ProductionEdge


router = APIRouter(
    prefix="/api/projects/{project_id}/graph",
    tags=["production-graph"],
)


def _service(request: Request):
    return request.app.state.production_graph_service


def _out(edge: ProductionEdge) -> dict:
    return {
        "id": edge.id,
        "upstream_type": edge.upstream_type,
        "upstream_id": edge.upstream_id,
        "upstream_version": edge.upstream_version,
        "downstream_type": edge.downstream_type,
        "downstream_id": edge.downstream_id,
        "relation": edge.relation,
        "created_at": edge.created_at,
    }


@router.post("/edges", response_model=ProductionEdgeOut, status_code=201)
def add_edge(project_id: str, payload: ProductionEdgeCreate, request: Request) -> dict:
    edge = _service(request).add_edge(
        project_id,
        payload.upstream_type,
        payload.upstream_id,
        payload.downstream_type,
        payload.downstream_id,
        relation=payload.relation,
        upstream_version=payload.upstream_version,
    )
    return _out(edge)


@router.get("/edges", response_model=list[ProductionEdgeOut])
def list_edges(project_id: str, request: Request) -> list[dict]:
    return [_out(edge) for edge in _service(request).list_edges(project_id)]


@router.get("/affected", response_model=AffectedNodesOut)
def affected_nodes(
    project_id: str, node_type: str, node_id: str, request: Request
) -> dict:
    affected = _service(request).affected_nodes(project_id, node_type, node_id)
    return {
        "changed_node": {"type": node_type, "id": node_id},
        "affected": affected,
    }


@router.delete("/edges/{edge_id}", status_code=204)
def remove_edge(project_id: str, edge_id: str, request: Request) -> None:
    edge = _service(request).get(edge_id)
    if edge.project_id != project_id:
        raise AppError(404, "edge_not_found", "生产依赖边不存在")
    _service(request).remove_edge(edge_id)
