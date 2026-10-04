"""Renders the OpenAPI description of the bridge (src/openapi.json) as the content of the "API reference" page.

Plain HTML in the style of the site, nothing loaded from elsewhere. Only what the description of Open Firenet uses is
supported: JSON and form bodies, object / array / scalar schemas, enumerations, ranges, references to named schemas.
"""
import html
import json
import re


def esc(text):
    return html.escape(str(text), quote=False)


def md(text):
    """The little Markdown used in the descriptions: paragraphs, `code` and **bold**."""
    out = []
    for para in re.split(r"\n\s*\n", str(text).strip()):
        t = esc(" ".join(para.split()))
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        out.append(t)
    return out


def inline(text):
    return " ".join(md(text)) if text else ""


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Renderer:
    def __init__(self, spec):
        self.spec = spec
        self.schemas = spec["components"]["schemas"]

    def deref(self, node):
        while "$ref" in node:
            target = self.spec
            for part in node["$ref"].lstrip("#/").split("/"):
                target = target[part]
            node = target
        return node

    def type_of(self, schema):
        """Short description of a type, with a link when it is a named schema."""
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[1]
            target = self.schemas.get(name, {})
            if target.get("type") not in ("object", None) and "enum" not in target:
                return self.type_of(target)                       # a named scalar: show the scalar
            if "enum" in target:
                return self.type_of(target)
            return f'<a href="#schema-{slug(name)}">{esc(name)}</a>'
        t = schema.get("type", "")
        if "enum" in schema:
            text = " | ".join(f"<code>{esc(v)}</code>" for v in schema["enum"])
        elif t == "array":
            text = "list of " + self.type_of(schema.get("items", {}))
        elif t == "object":
            extra = schema.get("additionalProperties")
            text = "object" + (f", any name → {self.type_of(extra)}" if isinstance(extra, dict) else "")
        else:
            text = esc(t)
        lo, hi = schema.get("minimum"), schema.get("maximum")
        if lo is not None and hi is not None:
            text += f", {lo} to {hi}"
        if schema.get("nullable"):
            text += " or <code>null</code>"
        return text

    def describe(self, schema):
        text = schema.get("description")
        if not text and "$ref" in schema:
            target = self.deref(schema)
            text = target.get("description") if target.get("type") != "object" or "enum" in target else None
        parts = [inline(text)] if text else []
        if "default" in schema:
            parts.append(f"Default: <code>{esc(schema['default'])}</code>.")
        return " ".join(parts)

    def fields(self, schema):
        """Table of the properties of an object schema."""
        schema = self.deref(schema)
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        rows = []
        for name, sub in props.items():
            req = ' <span class="req">required</span>' if name in required else ""
            rows.append(f"  <tr><td><code>{esc(name)}</code>{req}</td><td>{self.type_of(sub)}</td><td>{self.describe(sub)}</td></tr>")
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            rows.append(f"  <tr><td><i>any other name</i></td><td>{self.type_of(extra)}</td><td>{self.describe(extra)}</td></tr>")
        elif extra is True:
            rows.append("  <tr><td><i>other fields</i></td><td></td><td>Not described here.</td></tr>")
        if not rows:
            return ""
        return ('<div class="table-wrap">\n<table class="fields">\n  <tr><th>Field</th><th>Type</th><th>Description</th></tr>\n'
                + "\n".join(rows) + "\n</table>\n</div>")

    def body(self, schema):
        """A schema where it is used: a link for a named object, a table or a type otherwise."""
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[1]
            return f'<p>Fields: see <a href="#schema-{slug(name)}">{esc(name)}</a>.</p>'
        resolved = self.deref(schema)
        if resolved.get("type") == "object" and resolved.get("properties"):
            return self.fields(resolved)
        if resolved.get("type") == "array" and self.deref(resolved.get("items", {})).get("properties"):
            return "<p>A list of:</p>\n" + self.fields(resolved["items"])
        return f"<p>{self.type_of(resolved)}</p>"

    def operation(self, path, method, op):
        anchor = slug(f"{method}-{path}")
        out = [f'<div class="endpoint" id="{anchor}">',
               f'<h3><span class="method {method}">{method.upper()}</span> <code>{esc(path)}</code></h3>',
               f"<p><b>{esc(op.get('summary', ''))}</b></p>"]
        out += [f"<p>{p}</p>" for p in md(op.get("description", ""))] if op.get("description") else []
        for ctype, content in op.get("requestBody", {}).get("content", {}).items():
            out.append(f"<h4>Request body <small>{esc(ctype)}</small></h4>")
            out.append(self.body(content["schema"]))
            examples = [(e.get("summary", "Example"), e["value"]) for e in content.get("examples", {}).values()]
            if "example" in content:
                examples.append(("Example", content["example"]))
            for label, value in examples:
                out.append(f"<p>{esc(label)}:</p>\n<pre><code>{esc(json.dumps(value))}</code></pre>")
        for code, resp in op.get("responses", {}).items():
            resp = self.deref(resp)
            out.append(f"<h4>Answer {esc(code)} <small>{inline(resp.get('description', ''))}</small></h4>")
            for ctype, content in resp.get("content", {}).items():
                if ctype == "application/json":
                    out.append(self.body(content["schema"]))
                else:
                    out.append(f"<p><code>{esc(ctype)}</code></p>")
        out.append("</div>")
        return "\n".join(out)

    def render(self):
        info = self.spec["info"]
        out = [f"<h1>API reference</h1>",
               f'<p class="lead">Every endpoint of the bridge, with its fields, types, units and ranges. '
               f'Generated from the <a href="openapi.yaml">OpenAPI description</a> of firmware {esc(info["version"])}.</p>']
        out += [f"<p>{p}</p>" for p in md(info.get("description", ""))]
        # Summary table
        ops = [(p, m, op) for p, item in self.spec["paths"].items() for m, op in item.items()]
        tags = [t["name"] for t in self.spec.get("tags", [])]
        out.append('<h2>Endpoints</h2>\n<div class="table-wrap">\n<table>\n  <tr><th>Endpoint</th><th>Purpose</th></tr>')
        for tag in tags:
            for p, m, op in ops:
                if tag in op.get("tags", []):
                    out.append(f'  <tr><td><a href="#{slug(m + "-" + p)}"><span class="method {m}">{m.upper()}</span> '
                               f'<code>{esc(p)}</code></a></td><td>{esc(op.get("summary", ""))}</td></tr>')
        out.append("</table>\n</div>")
        for tag in tags:
            desc = next((t.get("description") for t in self.spec["tags"] if t["name"] == tag), None)
            out.append(f'<h2 id="{slug(tag)}">{esc(tag)}</h2>')
            if desc:
                out.append(f"<p>{inline(desc)}</p>")
            out += [self.operation(p, m, op) for p, m, op in ops if tag in op.get("tags", [])]
        out.append('<h2 id="schemas">Objects</h2>\n<p>The objects exchanged with the bridge, referred to above.</p>')
        for name, schema in self.schemas.items():
            if schema.get("type") != "object":
                continue
            out.append(f'<h3 id="schema-{slug(name)}">{esc(name)}</h3>')
            if schema.get("description"):
                out += [f"<p>{p}</p>" for p in md(schema["description"])]
            out.append(self.fields(schema))
        return "\n".join(out)


def render(spec):
    return Renderer(spec).render()
