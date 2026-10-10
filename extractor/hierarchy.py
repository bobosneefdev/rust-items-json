"""Walk prefab GameObject hierarchies, keeping positions relative to the chosen root."""


def rotate(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return [vx + w * tx + y * tz - z * ty, vy + w * ty + z * tx - x * tz, vz + w * tz + x * ty - y * tx]


def multiply(a, b):
    x, y, z, w = a
    X, Y, Z, W = b
    return [w * X + x * W + y * Z - z * Y, w * Y - x * Z + y * W + z * X,
            w * Z + x * Y - y * X + z * W, w * W - x * X - y * Y - z * Z]


def nodes(g, file, root):
    seen = set()

    def visit(file, pid, position, rotation, scale, active, path, is_root=False):
        key = file, pid
        if key in seen:
            raise ValueError(f"cyclic/shared GameObject hierarchy: {key}")
        seen.add(key)
        go = g._read(file, pid)
        if go is None:
            raise ValueError(f"missing GameObject: {key}")
        components, transform, colliders = [], None, []
        for ref in go["m_Component"]:
            loc = g.resolve(file, ref["component"])
            if not loc:
                continue
            t = g._read(*loc)
            if t is None:
                raise ValueError(f"unreadable prefab component: {loc}")
            t.setdefault("__pid", loc[1])
            if g.files[loc[0]].objects[loc[1]].type.name.endswith("Collider"):
                colliders.append({"type": g.files[loc[0]].objects[loc[1]].type.name, **{k.removeprefix("m_"): v for k, v in t.items() if k in {"m_Enabled", "m_Center", "m_Size", "m_Radius", "m_Height", "m_Direction"}}})
            if "m_Children" in t:
                transform = loc[0], t
            else:
                cls = g.class_of(loc[0], t)
                if cls:
                    components.append((cls, loc[0], t))
        if transform and not is_root:
            t = transform[1]
            offset = rotate(rotation, [t["m_LocalPosition"][a] * scale[i] for i, a in enumerate("xyz")])
            position = [position[i] + offset[i] for i in range(3)]
            rotation = multiply(rotation, [t["m_LocalRotation"][a] for a in "xyzw"])
            scale = [scale[i] * t["m_LocalScale"][a] for i, a in enumerate("xyz")]
        active = active and bool(go.get("m_IsActive", True))
        path = path + [go["m_Name"]]
        yield {"file": file, "id": pid, "name": go["m_Name"], "path": path, "position": position,
               "rotation": rotation, "scale": scale, "active": active, "components": components, "colliders": colliders}
        if transform:
            for child in transform[1]["m_Children"]:
                loc = g.resolve(transform[0], child)
                if not loc:
                    raise ValueError("missing child transform")
                t = g._read(*loc)
                go_loc = g.resolve(loc[0], t["m_GameObject"])
                yield from visit(*go_loc, position, rotation, scale, active, path)

    yield from visit(file, root, [0, 0, 0], [0, 0, 0, 1], [1, 1, 1], True, [], True)


def prefab_nodes(g, prefab):
    components = g.prefabs.get(prefab, [])
    if components:
        _, file, t = components[0]
        loc = g.resolve(file, t["m_GameObject"])
        yield from nodes(g, *loc)
