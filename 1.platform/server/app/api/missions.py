"""Mission endpoints: create, inspect, diff, patch download, abort."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import AppState, get_state, require_live_access
from app.core.models import DiffFile, Mission, MissionCreate, MissionDetail, new_id, validate_repo_url
from app.core.runner import MissionRunner, RunnerDeps

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_live_access)])
async def create_mission(body: MissionCreate, state: AppState = Depends(get_state)) -> dict[str, str]:
    repo_url: str | None = None
    if body.repo_url:
        try:
            repo_url = validate_repo_url(body.repo_url, allow_local=state.settings.allow_local_repos)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.swe_instance_id and state.swe.get(body.swe_instance_id) is None:
        raise HTTPException(status_code=422, detail="unknown SWE-bench instance id")
    mission = Mission(
        id=new_id("m"),
        type=body.type,
        repo_url=repo_url,
        git_ref=body.git_ref,
        test_command=body.test_command,
        install_command=body.install_command,
        swe_instance_id=body.swe_instance_id,
        hint=body.hint,
    )
    await state.store.save_mission(mission)
    deps = RunnerDeps(
        store=state.store,
        bus=state.bus,
        sandbox=state.sandbox,
        llm_factory=state.llm_factory,
        grounder=state.grounder,
        prices=state.prices,
        settings=state.settings,
        swe=state.swe,
        on_finished=_recorder_hook(state),
    )
    state.registry.start(MissionRunner(mission, deps))
    return {
        "id": mission.id,
        "status": mission.status.value,
        "stream": f"/api/v1/missions/{mission.id}/events",
    }


def _recorder_hook(state: AppState):  # type: ignore[no-untyped-def]
    async def hook(m: Mission) -> None:
        if state.settings.env == "development" or m.status.value == "VERIFIED":
            try:
                await state.recorder.record(m)
            except Exception:  # noqa: BLE001, S110
                pass

    return hook


@router.get("", response_model=list[Mission])
async def list_missions(state: AppState = Depends(get_state)) -> list[Mission]:
    return await state.store.list_missions()


@router.get("/{mission_id}", response_model=MissionDetail)
async def get_mission(mission_id: str, state: AppState = Depends(get_state)) -> MissionDetail:
    detail = await state.store.get_detail(mission_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return detail


@router.get("/{mission_id}/diff", response_model=list[DiffFile])
async def get_diff(mission_id: str, state: AppState = Depends(get_state)) -> list[DiffFile]:
    m = await state.store.get_mission(mission_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mission not found")
    if m.diff:
        return m.diff
    if m.replay_of:
        data = state.recorder.load(m.replay_of)
        if data:
            return [DiffFile.model_validate(d) for d in data.get("mission", {}).get("diff", [])]
    return []


@router.get("/{mission_id}/patch")
async def get_patch(mission_id: str, state: AppState = Depends(get_state)) -> Response:
    m = await state.store.get_mission(mission_id)
    if m is None:
        raise HTTPException(status_code=404, detail="mission not found")
    attempts = await state.store.attempts(mission_id)
    selected = next((a for a in attempts if a.selected), None)
    if selected is None and m.replay_of:
        data = state.recorder.load(m.replay_of) or {}
        for raw in data.get("attempts", []):
            if raw.get("selected"):
                return Response(
                    content=raw["patch"],
                    media_type="text/x-patch",
                    headers={"Content-Disposition": f'attachment; filename="archon-{mission_id}.patch"'},
                )
    if selected is None:
        raise HTTPException(status_code=404, detail="no verified patch for this mission")
    return Response(
        content=selected.patch,
        media_type="text/x-patch",
        headers={"Content-Disposition": f'attachment; filename="archon-{mission_id}.patch"'},
    )


@router.post("/{mission_id}/abort")
async def abort_mission(mission_id: str, state: AppState = Depends(get_state)) -> dict[str, bool]:
    if await state.store.get_mission(mission_id) is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return {"aborted": state.registry.abort(mission_id)}
