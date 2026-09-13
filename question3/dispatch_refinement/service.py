"""Public-information dispatch with service and endpoint cost proxies.

SERVICE_PAIR plans two tasks, so it does not precommit to completing every
currently remaining scan. SERVICE_TOUR retains a full open tour as a control.
Both only choose the next existing task; the original policy still executes it.
The cost is a deterministic proxy, not a time bound or an expected value.
"""
import math

from question3.innovation.geometry import bbox, parallax_point


def choose(current, tasks, context):
    """Return an unchanged (kind, id, point) task and diagnostic details."""
    if not tasks:
        raise ValueError("Service dispatch requires at least one task")
    variant = context.get("config", {}).get("dispatch_variant", "service_pair").lower()
    if variant not in ("service_pair", "service_tour"):
        raise ValueError(f"Unknown service dispatch variant: {variant}")
    tasks = list(tasks)
    known = set(context["first"]) | set(context["cleared"])
    unknown = [c for c in range(1, 21) if c not in known]
    models = []
    for kind, target, point in tasks:
        if kind == "scan":
            models.append(dict(end=tuple(point), channels=unknown,
                               action_s=5.0 * len(unknown), direct=tuple(point)))
        elif kind == "localize":
            centre, radius, *_ = bbox(context["polys"][target], context["bearings"][target])
            clearable = radius <= 20.0 - 1e-5
            # For an uncertain source, price one radio measurement and one
            # optical+laser action. Further measurements are not predicted.
            # The current centre is only a service-endpoint proxy.
            models.append(dict(end=tuple(centre), channels=[] if clearable else [target],
                               action_s=5.0 if clearable else 10.0,
                               direct=tuple(centre) if clearable else None))
        else:
            raise ValueError(f"Unknown dispatch task kind: {kind}")

    n = len(tasks)
    # Row n represents the real current position; other rows represent the
    # preceding task's estimated endpoint. Geometric work is done once.
    positions = [m["end"] for m in models] + [tuple(current)]
    travel = [[0.0] * n for _ in positions]
    entries = [[None] * n for _ in positions]
    for previous, position in enumerate(positions):
        for j, model in enumerate(models):
            point = model["direct"]
            if point is None:
                target = tasks[j][1]
                point, _ = parallax_point(context["polys"][target],
                                          context["bearings"][target], position)
            point = tuple(float(x) for x in point)
            entries[previous][j] = point
            travel[previous][j] = (math.dist(position, point)
                                   + math.dist(point, model["end"])) / 5.0

    def leg(previous, channel, j):
        model = models[j]
        channels = model["channels"]
        switches = len(channels) - int(bool(channels) and channel == channels[0])
        after_channel = channels[-1] if channels else channel
        return travel[previous][j] + model["action_s"] + switches, after_channel

    initial_channel = context.get("channel")

    def cost(route):
        total, previous, channel = 0.0, n, initial_channel
        for j in route:
            value, channel = leg(previous, channel, j)
            total += value
            previous = j
        return total

    candidates = []
    for start in range(n):
        route = [start]
        left = set(range(n)) - {start}
        _, channel = leg(n, initial_channel, start)
        if variant == "service_pair":
            if left:
                following = min(left, key=lambda j: (leg(start, channel, j)[0], j))
                route.append(following)
        else:
            while left:
                following = min(left, key=lambda j: (leg(route[-1], channel, j)[0], j))
                _, channel = leg(route[-1], channel, following)
                route.append(following)
                left.remove(following)
            # Strictly improving two-opt, including the initial task. The
            # directed service costs are recomputed for each reversed route.
            while True:
                old = cost(route)
                improvement = None
                for i in range(n - 1):
                    for j in range(i + 1, n):
                        alternative = route[:i] + list(reversed(route[i:j + 1])) + route[j + 1:]
                        value = cost(alternative)
                        if value < old - 1e-7 and (improvement is None or
                                                  (value, alternative) < improvement):
                            improvement = (value, alternative)
                if improvement is None:
                    break
                route = improvement[1]
        candidates.append((cost(route), route))
    score, route = min(candidates)
    selected = route[0]
    immediate, _ = leg(n, initial_channel, selected)
    return tasks[selected], dict(
        method=variant, cost_kind="deterministic_service_proxy_not_bound",
        score_s=score, immediate_proxy_s=immediate,
        estimated_entry=list(entries[n][selected]),
        estimated_endpoint=list(models[selected]["end"]),
        unknown_channel_count=len(unknown), horizon_tasks=len(route),
        tour=[dict(task=tasks[j][0], target=tasks[j][1], point=list(tasks[j][2])) for j in route],
    )
