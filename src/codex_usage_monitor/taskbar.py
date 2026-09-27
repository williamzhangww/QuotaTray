from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains_point(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def intersects(self, other: "Rect") -> bool:
        return (
            self.left < other.right
            and self.right > other.left
            and self.top < other.bottom
            and self.bottom > other.top
        )


@dataclass(frozen=True)
class Size:
    width: int
    height: int


@dataclass(frozen=True)
class Point:
    x: int
    y: int


def detect_taskbar_edge(screen: Rect, available: Rect) -> str:
    if available.bottom < screen.bottom:
        return "bottom"
    if available.top > screen.top:
        return "top"
    if available.left > screen.left:
        return "left"
    if available.right < screen.right:
        return "right"
    return "bottom"


def recommended_dock_position(
    screen: Rect,
    available: Rect,
    dock_size: Size,
    margin: int = 8,
) -> Point:
    edge = detect_taskbar_edge(screen, available)
    width = max(1, dock_size.width)
    height = max(1, dock_size.height)

    if edge == "top":
        x = available.right - width - margin
        y = available.top + margin
    elif edge == "left":
        x = available.left + margin
        y = available.bottom - height - margin
    elif edge == "right":
        x = available.right - width - margin
        y = available.bottom - height - margin
    else:
        x = available.right - width - margin
        y = available.bottom - height - margin

    return clamp_point_to_visible_area(Point(x, y), dock_size, (available,), margin)


def clamp_point_to_visible_area(
    point: Point,
    dock_size: Size,
    visible_areas: tuple[Rect, ...],
    margin: int = 8,
) -> Point:
    if not visible_areas:
        return point

    width = max(1, dock_size.width)
    height = max(1, dock_size.height)
    current = Rect(point.x, point.y, width, height)
    if any(area.intersects(current) for area in visible_areas):
        area = next(area for area in visible_areas if area.intersects(current))
    else:
        area = visible_areas[0]

    min_x = area.left + margin
    max_x = max(min_x, area.right - width - margin)
    min_y = area.top + margin
    max_y = max(min_y, area.bottom - height - margin)
    return Point(
        min(max(point.x, min_x), max_x),
        min(max(point.y, min_y), max_y),
    )


def recover_saved_position(
    saved: Point | None,
    dock_size: Size,
    visible_areas: tuple[Rect, ...],
    fallback: Point,
    margin: int = 8,
) -> Point:
    if saved is None:
        return fallback
    current = Rect(saved.x, saved.y, max(1, dock_size.width), max(1, dock_size.height))
    if any(area.intersects(current) for area in visible_areas):
        return clamp_point_to_visible_area(saved, dock_size, visible_areas, margin)
    return fallback
