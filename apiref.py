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


# Fixed words of the page, per language. The texts of the description itself are translated by a table given to render().
LABELS = {
    "en": {"title": "API reference", "lead": "Every endpoint of the bridge, with its fields, types, units and ranges. "
           "Generated from the {link}OpenAPI description</a> of firmware {version}.", "endpoints": "Endpoints",
           "endpoint": "Endpoint", "purpose": "Purpose", "objects": "Objects",
           "objects_lead": "The objects exchanged with the bridge, referred to above.", "field": "Field", "type": "Type",
           "description": "Description", "required": "required", "any_name": "any other name", "other_fields": "other fields",
           "not_described": "Not described here.", "list_of": "list of", "object": "object", "any_name_to": "any name",
           "range": "{lo} to {hi}", "or_null": "or", "default": "Default: {value}.", "fields_see": "Fields: see", "a_list_of": "A list of:",
           "request_body": "Request body", "example": "Example", "answer": "Answer"},
    "fr": {"title": "Référence de l'API", "lead": "Toutes les adresses de la clé, avec leurs champs, types, unités et plages. "
           "Générée à partir de la {link}description OpenAPI</a> du firmware {version}.", "endpoints": "Adresses",
           "endpoint": "Adresse", "purpose": "Rôle", "objects": "Objets",
           "objects_lead": "Les objets échangés avec la clé, cités plus haut.", "field": "Champ", "type": "Type",
           "description": "Description", "required": "obligatoire", "any_name": "tout autre nom", "other_fields": "autres champs",
           "not_described": "Non décrits ici.", "list_of": "liste de", "object": "objet", "any_name_to": "tout nom",
           "range": "{lo} à {hi}", "or_null": "ou", "default": "Par défaut : {value}.", "fields_see": "Champs : voir", "a_list_of": "Une liste de :",
           "request_body": "Corps de la requête", "example": "Exemple", "answer": "Réponse"},
}


def texts(spec):
    """The texts of the description that are shown on the page, in the order they appear: what a translation covers."""
    out = []
    def add(text):
        if isinstance(text, str) and text.strip() and text not in out:
            out.append(text)
    def walk(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("description", "summary") and isinstance(v, str):
                    add(v)
                else:
                    walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
    for tag in spec.get("tags", []):
        add(tag["name"])
    walk(spec)
    return out


class Renderer:
    def __init__(self, spec, lang="en", table=None):
        self.spec = spec
        self.schemas = spec["components"]["schemas"]
        self.l = LABELS[lang]
        self.table = table or {}

    def tr(self, text):
        """A text of the description in the page's language (English when it has no translation)."""
        return self.table.get(text) or text

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
            text = self.l["list_of"] + " " + self.type_of(schema.get("items", {}))
        elif t == "object":
            extra = schema.get("additionalProperties")
            text = self.l["object"] + (f", {self.l['any_name_to']} → {self.type_of(extra)}" if isinstance(extra, dict) else "")
        else:
            text = esc(t)
        lo, hi = schema.get("minimum"), schema.get("maximum")
        if lo is not None and hi is not None:
            text += ", " + self.l["range"].format(lo=lo, hi=hi)
        if schema.get("nullable"):
            text += f" {self.l['or_null']} <code>null</code>"
        return text

    def describe(self, schema):
        text = schema.get("description")
        if not text and "$ref" in schema:
            target = self.deref(schema)
            text = target.get("description") if target.get("type") != "object" or "enum" in target else None
        parts = [inline(self.tr(text))] if text else []
        if "default" in schema:
            parts.append(self.l["default"].format(value=f"<code>{esc(schema['default'])}</code>"))
        return " ".join(parts)

    def fields(self, schema):
        """Table of the properties of an object schema."""
        schema = self.deref(schema)
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        rows = []
        for name, sub in props.items():
            req = f' <span class="req">{self.l["required"]}</span>' if name in required else ""
            rows.append(f"  <tr><td><code>{esc(name)}</code>{req}</td><td>{self.type_of(sub)}</td><td>{self.describe(sub)}</td></tr>")
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            rows.append(f"  <tr><td><i>{self.l['any_name']}</i></td><td>{self.type_of(extra)}</td><td>{self.describe(extra)}</td></tr>")
        elif extra is True:
            rows.append(f"  <tr><td><i>{self.l['other_fields']}</i></td><td></td><td>{self.l['not_described']}</td></tr>")
        if not rows:
            return ""
        return ('<div class="table-wrap">\n<table class="fields">\n'
                f'  <tr><th>{self.l["field"]}</th><th>{self.l["type"]}</th><th>{self.l["description"]}</th></tr>\n'
                + "\n".join(rows) + "\n</table>\n</div>")

    def body(self, schema):
        """A schema where it is used: a link for a named object, a table or a type otherwise."""
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[1]
            return f'<p>{self.l["fields_see"]} <a href="#schema-{slug(name)}">{esc(name)}</a>.</p>'
        resolved = self.deref(schema)
        if resolved.get("type") == "object" and resolved.get("properties"):
            return self.fields(resolved)
        if resolved.get("type") == "array" and self.deref(resolved.get("items", {})).get("properties"):
            return f"<p>{self.l['a_list_of']}</p>\n" + self.fields(resolved["items"])
        return f"<p>{self.type_of(resolved)}</p>"

    def operation(self, path, method, op):
        anchor = slug(f"{method}-{path}")
        out = [f'<div class="endpoint" id="{anchor}">',
               f'<h3><span class="method {method}">{method.upper()}</span> <code>{esc(path)}</code></h3>',
               f"<p><b>{esc(self.tr(op.get('summary', '')))}</b></p>"]
        out += [f"<p>{p}</p>" for p in md(self.tr(op.get("description", "")))] if op.get("description") else []
        for ctype, content in op.get("requestBody", {}).get("content", {}).items():
            out.append(f"<h4>{self.l['request_body']} <small>{esc(ctype)}</small></h4>")
            out.append(self.body(content["schema"]))
            examples = [(self.tr(e.get("summary", "")) or self.l["example"], e["value"]) for e in content.get("examples", {}).values()]
            if "example" in content:
                examples.append((self.l["example"], content["example"]))
            for label, value in examples:
                out.append(f"<p>{esc(label)}:</p>\n<pre><code>{esc(json.dumps(value))}</code></pre>")
        for code, resp in op.get("responses", {}).items():
            resp = self.deref(resp)
            out.append(f"<h4>{self.l['answer']} {esc(code)} <small>{inline(self.tr(resp.get('description', '')))}</small></h4>")
            for ctype, content in resp.get("content", {}).items():
                if ctype == "application/json":
                    out.append(self.body(content["schema"]))
                else:
                    out.append(f"<p><code>{esc(ctype)}</code></p>")
        out.append("</div>")
        return "\n".join(out)

    def render(self):
        info = self.spec["info"]
        out = [f"<h1>{self.l['title']}</h1>",
               '<p class="lead">' + self.l["lead"].format(link='<a href="openapi.yaml">', version=esc(info["version"])) + "</p>"]
        out += [f"<p>{p}</p>" for p in md(self.tr(info.get("description", "")))]
        # Summary table
        ops = [(p, m, op) for p, item in self.spec["paths"].items() for m, op in item.items()]
        tags = [t["name"] for t in self.spec.get("tags", [])]
        out.append(f'<h2>{self.l["endpoints"]}</h2>\n<div class="table-wrap">\n<table>\n'
                   f'  <tr><th>{self.l["endpoint"]}</th><th>{self.l["purpose"]}</th></tr>')
        for tag in tags:
            for p, m, op in ops:
                if tag in op.get("tags", []):
                    out.append(f'  <tr><td><a href="#{slug(m + "-" + p)}"><span class="method {m}">{m.upper()}</span> '
                               f'<code>{esc(p)}</code></a></td><td>{esc(self.tr(op.get("summary", "")))}</td></tr>')
        out.append("</table>\n</div>")
        for tag in tags:
            desc = next((t.get("description") for t in self.spec["tags"] if t["name"] == tag), None)
            out.append(f'<h2 id="{slug(tag)}">{esc(self.tr(tag))}</h2>')
            if desc:
                out.append(f"<p>{inline(self.tr(desc))}</p>")
            out += [self.operation(p, m, op) for p, m, op in ops if tag in op.get("tags", [])]
        out.append(f'<h2 id="schemas">{self.l["objects"]}</h2>\n<p>{self.l["objects_lead"]}</p>')
        for name, schema in self.schemas.items():
            if schema.get("type") != "object":
                continue
            out.append(f'<h3 id="schema-{slug(name)}">{esc(name)}</h3>')
            if schema.get("description"):
                out += [f"<p>{p}</p>" for p in md(self.tr(schema["description"]))]
            out.append(self.fields(schema))
        return "\n".join(out)


def render(spec, lang="en", table=None):
    return Renderer(spec, lang, table).render()
