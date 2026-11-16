"""Patch selected direct text nodes, retaining comments and unselected nodes."""

import hashlib
from xml.dom import minidom, Node
from .contracts import TranslationError


def text_hash(value):
    return hashlib.sha256(value.strip().encode()).hexdigest()


def parse(data):
    if isinstance(data, str):
        data = data.encode()
    if len(data) > 10 * 1024 * 1024 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise TranslationError("invalid_nfo", "NFO 太大或包含不支持的实体声明")
    try:
        return minidom.parseString(data)
    except Exception:
        raise TranslationError("invalid_nfo", "NFO XML 无效") from None


def nodes(doc, field):
    return [
        n
        for n in doc.documentElement.childNodes
        if n.nodeType == Node.ELEMENT_NODE and n.tagName == field
    ]


def texts(doc):
    result = {}
    for field in ("title", "plot", "outline", "tagline"):
        matches = nodes(doc, field)
        # Multiple narrative nodes have no unambiguous single-field replacement.
        if len(matches) > 1:
            result[field] = None
        elif matches:
            result[field] = "".join(
                n.data
                for n in matches[0].childNodes
                if n.nodeType in {Node.TEXT_NODE, Node.CDATA_SECTION_NODE}
            ).strip()
        else:
            result[field] = ""
    return result


def patch(data, replacements):
    doc = parse(data)
    current = texts(doc)
    changed = []
    for field, value in replacements.items():
        if current[field] is None:
            raise TranslationError("invalid_nfo", "同名文字节点重复，需人工确认")
        if current[field] == value.strip():
            continue
        match = nodes(doc, field)
        node = match[0] if match else doc.createElement(field)
        if not match:
            doc.documentElement.appendChild(node)
        if any(n.nodeType == Node.ELEMENT_NODE for n in node.childNodes):
            raise TranslationError("invalid_nfo", "文字节点内含子元素，未自动覆盖")
        # Retain comments within the selected node as well.
        for child in list(node.childNodes):
            if child.nodeType in {Node.TEXT_NODE, Node.CDATA_SECTION_NODE}:
                node.removeChild(child)
        node.appendChild(doc.createTextNode(value))
        changed.append(field)
    raw = data.encode() if isinstance(data, str) else data
    return (doc.toxml(encoding="utf-8") if changed else raw), changed
