from __future__ import annotations

import base64
import hashlib
import secrets
import shutil
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, unquote, urlparse
from uuid import uuid4
from xml.etree import ElementTree as ET

import httpx

__all__ = [
    "_camera_http_url_or_none",
    "_camera_rtsp_url_or_none",
    "_camera_stream_url_with_credentials",
    "_camera_snapshot_bytes_from_stream",
    "_xml_local_name",
    "_onvif_wsse_security_header",
    "_onvif_soap_request",
    "_find_first_descendant_text",
    "_find_media_service_xaddr",
    "_test_onvif_camera_connection",
    "_discover_onvif_devices",
]


def _camera_http_url_or_none(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return raw


def _camera_rtsp_url_or_none(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    if parsed.scheme.lower() not in {"rtsp", "rtsps"}:
        return None
    if not parsed.netloc:
        return None
    return raw


def _camera_stream_url_with_credentials(stream_url: str, *, username: str | None, password: str | None) -> str:
    parsed = urlparse(str(stream_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(stream_url or "").strip()
    if parsed.username or not username:
        return parsed.geturl()
    safe_username = quote(str(username), safe="")
    safe_password = quote(str(password or ""), safe="")
    auth_part = safe_username if safe_password == "" else f"{safe_username}:{safe_password}"
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = auth_part + "@"
    if host:
        netloc += host
    if parsed.port:
        netloc += f":{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def _camera_snapshot_bytes_from_stream(stream_url: str, *, username: str | None, password: str | None) -> bytes:
    ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    resolved_url = _camera_stream_url_with_credentials(stream_url, username=username, password=password)
    proc = subprocess.run(
        [
            ffmpeg_bin,
            "-v",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            resolved_url,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        stderr_text = proc.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(stderr_text or "ffmpeg snapshot capture failed")
    return proc.stdout


def _xml_local_name(tag: str) -> str:
    raw = str(tag or "")
    return raw.split("}", 1)[-1] if "}" in raw else raw


def _onvif_wsse_security_header(username: str, password: str) -> str:
    nonce_bytes = secrets.token_bytes(16)
    created = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    digest = base64.b64encode(hashlib.sha1(nonce_bytes + created.encode("utf-8") + password.encode("utf-8")).digest()).decode("ascii")
    nonce_b64 = base64.b64encode(nonce_bytes).decode("ascii")
    return f"""
<wsse:Security soap:mustUnderstand="1"
 xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
 xmlns:wsu="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd">
  <wsse:UsernameToken>
    <wsse:Username>{username}</wsse:Username>
    <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">{digest}</wsse:Password>
    <wsse:Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{nonce_b64}</wsse:Nonce>
    <wsu:Created>{created}</wsu:Created>
  </wsse:UsernameToken>
</wsse:Security>
""".strip()


def _onvif_soap_request(
    service_url: str,
    body_xml: str,
    *,
    username: str | None,
    password: str | None,
    timeout: float = 8.0,
) -> ET.Element:
    service = _camera_http_url_or_none(service_url)
    if service is None:
        raise ValueError("유효한 ONVIF 장치 URL이 아닙니다.")
    header_parts = [f"<wsa:MessageID>uuid:{uuid4()}</wsa:MessageID>"]
    if username:
        header_parts.append(_onvif_wsse_security_header(username, password or ""))
    envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
 xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing">
  <soap:Header>
    {''.join(header_parts)}
  </soap:Header>
  <soap:Body>
    {body_xml}
  </soap:Body>
</soap:Envelope>
""".strip()
    auth = (username, password or "") if username else None
    with httpx.Client(timeout=timeout, follow_redirects=True, verify=False) as client:
        response = client.post(
            service,
            content=envelope.encode("utf-8"),
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
            auth=auth,
        )
    response.raise_for_status()
    return ET.fromstring(response.content)


def _find_first_descendant_text(element: ET.Element, local_name: str) -> str | None:
    target = str(local_name or "").strip()
    if not target:
        return None
    for node in element.iter():
        if _xml_local_name(node.tag) == target:
            value = str(node.text or "").strip()
            if value:
                return value
    return None


def _find_media_service_xaddr(root: ET.Element) -> str | None:
    for node in root.iter():
        if _xml_local_name(node.tag) in {"Media", "Media2"}:
            xaddr = _find_first_descendant_text(node, "XAddr")
            if _camera_http_url_or_none(xaddr):
                return xaddr
    for service in root.iter():
        if _xml_local_name(service.tag) != "Service":
            continue
        namespace_text = _find_first_descendant_text(service, "Namespace") or ""
        if "media/wsdl" not in namespace_text.lower():
            continue
        xaddr = _find_first_descendant_text(service, "XAddr")
        if _camera_http_url_or_none(xaddr):
            return xaddr
    return None


def _test_onvif_camera_connection(
    device_service_url: str,
    *,
    username: str | None,
    password: str | None,
) -> dict[str, Any]:
    device_root = _onvif_soap_request(
        device_service_url,
        '<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl"><tds:Category>All</tds:Category></tds:GetCapabilities>',
        username=username,
        password=password,
    )
    media_service_url = _find_media_service_xaddr(device_root)
    if not media_service_url:
        services_root = _onvif_soap_request(
            device_service_url,
            '<tds:GetServices xmlns:tds="http://www.onvif.org/ver10/device/wsdl"><tds:IncludeCapability>false</tds:IncludeCapability></tds:GetServices>',
            username=username,
            password=password,
        )
        media_service_url = _find_media_service_xaddr(services_root)

    manufacturer = None
    model = None
    firmware_version = None
    serial_number = None
    hardware_id = None
    try:
        info_root = _onvif_soap_request(
            device_service_url,
            '<tds:GetDeviceInformation xmlns:tds="http://www.onvif.org/ver10/device/wsdl" />',
            username=username,
            password=password,
        )
        manufacturer = _find_first_descendant_text(info_root, "Manufacturer")
        model = _find_first_descendant_text(info_root, "Model")
        firmware_version = _find_first_descendant_text(info_root, "FirmwareVersion")
        serial_number = _find_first_descendant_text(info_root, "SerialNumber")
        hardware_id = _find_first_descendant_text(info_root, "HardwareId")
    except httpx.HTTPStatusError:
        pass

    profile_token = None
    snapshot_url = None
    stream_url = None

    if media_service_url:
        try:
            profiles_root = _onvif_soap_request(
                media_service_url,
                '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl" />',
                username=username,
                password=password,
            )
            for node in profiles_root.iter():
                if _xml_local_name(node.tag) == "Profiles":
                    profile_token = str(node.attrib.get("token") or node.attrib.get("{http://www.onvif.org/ver10/media/wsdl}token") or "").strip() or None
                    if profile_token:
                        break
        except httpx.HTTPStatusError:
            profile_token = None
        if profile_token:
            try:
                snapshot_root = _onvif_soap_request(
                    media_service_url,
                    f'<trt:GetSnapshotUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl"><trt:ProfileToken>{profile_token}</trt:ProfileToken></trt:GetSnapshotUri>',
                    username=username,
                    password=password,
                )
                snapshot_url = _find_first_descendant_text(snapshot_root, "Uri")
            except Exception:
                snapshot_url = None
            try:
                stream_root = _onvif_soap_request(
                    media_service_url,
                    (
                        '<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">'
                        '<trt:StreamSetup><tt:Stream>RTP-Unicast</tt:Stream><tt:Transport><tt:Protocol>RTSP</tt:Protocol></tt:Transport></trt:StreamSetup>'
                        f'<trt:ProfileToken>{profile_token}</trt:ProfileToken>'
                        '</trt:GetStreamUri>'
                    ),
                    username=username,
                    password=password,
                )
                stream_url = _find_first_descendant_text(stream_root, "Uri")
            except Exception:
                stream_url = None

    return {
        "device_service_url": _camera_http_url_or_none(device_service_url) or str(device_service_url).strip(),
        "media_service_url": _camera_http_url_or_none(media_service_url),
        "profile_token": profile_token,
        "snapshot_url": _camera_http_url_or_none(snapshot_url) or snapshot_url,
        "stream_url": str(stream_url or "").strip() or None,
        "manufacturer": manufacturer,
        "model": model,
        "firmware_version": firmware_version,
        "serial_number": serial_number,
        "hardware_id": hardware_id,
    }


def _discover_onvif_devices(timeout_seconds: float = 2.5) -> list[dict[str, Any]]:
    timeout = max(0.5, min(10.0, float(timeout_seconds or 2.5)))
    probe = f"""<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
  <e:Header>
    <w:MessageID>uuid:{uuid4()}</w:MessageID>
    <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
    <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
  </e:Header>
  <e:Body>
    <d:Probe>
      <d:Types>dn:NetworkVideoTransmitter</d:Types>
    </d:Probe>
  </e:Body>
</e:Envelope>
""".strip()
    namespaces = {
        "a": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
        "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    }
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(0.35)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except OSError:
        pass
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    except OSError:
        pass
    try:
        try:
            sock.sendto(probe.encode("utf-8"), ("239.255.255.250", 3702))
        except OSError:
            return []
        deadline = time.time() + timeout
        found: dict[str, dict[str, Any]] = {}
        while time.time() < deadline:
            try:
                packet, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                root = ET.fromstring(packet)
            except ET.ParseError:
                continue
            for match in root.findall(".//d:ProbeMatch", namespaces):
                endpoint_reference = str(match.findtext("./a:EndpointReference/a:Address", default="", namespaces=namespaces) or "").strip() or None
                raw_xaddrs = str(match.findtext("./d:XAddrs", default="", namespaces=namespaces) or "").strip()
                xaddr_candidates = [value.strip() for value in raw_xaddrs.split() if _camera_http_url_or_none(value.strip())]
                onvif_device_url = xaddr_candidates[0] if xaddr_candidates else None
                scopes = [value.strip() for value in str(match.findtext("./d:Scopes", default="", namespaces=namespaces) or "").split() if value.strip()]
                types = [value.strip() for value in str(match.findtext("./d:Types", default="", namespaces=namespaces) or "").split() if value.strip()]
                host = None
                if onvif_device_url:
                    try:
                        host = urlparse(onvif_device_url).hostname
                    except Exception:
                        host = None
                if not host:
                    host = str(addr[0] or "").strip() or None
                camera_name = None
                for scope in scopes:
                    if "/name/" in scope:
                        camera_name = unquote(scope.split("/name/", 1)[1]).replace("_", " ").strip() or None
                        break
                key = str(onvif_device_url or endpoint_reference or host or uuid4())
                found[key] = {
                    "endpoint_reference": endpoint_reference,
                    "camera_name": camera_name,
                    "host": host,
                    "onvif_device_url": onvif_device_url,
                    "scopes": scopes,
                    "types": types,
                }
    finally:
        sock.close()
    return sorted(
        found.values(),
        key=lambda row: (
            str(row.get("host") or ""),
            str(row.get("camera_name") or ""),
            str(row.get("onvif_device_url") or ""),
        ),
    )
