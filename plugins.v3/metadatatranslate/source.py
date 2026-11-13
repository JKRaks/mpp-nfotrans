"""Read TMDB translations using the host's authenticated API client."""
import re
from .config import locale
from .contracts import TranslationError

FIELD_SOURCE = {"title": "title", "plot": "overview", "outline": "overview", "tagline": "tagline"}


def placeholder(value):
    return bool(re.fullmatch(r"(?:第\s*\d+\s*[集季话]|(?:episode|season|集|季)\s*\d+)", value.strip(), re.I))


def source_identity(meta, info, season=None, episode=None):
    from app.sdk.config import settings
    source = getattr(info, "scrape_source", None) or settings.SCRAP_SOURCE
    if source != "themoviedb" or not getattr(info, "tmdb_id", None):
        raise TranslationError("unsupported_source", "本期仅支持已确认 TMDB 身份的媒体")
    kind = "movie" if getattr(getattr(info, "type", None), "value", "") in {"电影", "Movie", "movie"} else "tv"
    if kind != "movie" and season is not None: kind = "episode" if episode is not None else "season"
    return {"kind": kind, "tmdb_id": int(info.tmdb_id), "season": season, "episode": episode,
            "lookup_episode": getattr(meta, "begin_episode", None) or episode,
            "episode_group": getattr(info, "episode_group", None), "original_language": getattr(info, "original_language", None),
            "title": getattr(info, "title", "") or ""}


class TmdbSource:
    def fetch(self, identity):
        from app.modules.themoviedb.tmdbapi import TmdbApi
        client = TmdbApi(language="en-US")
        kind, media_id = identity["kind"], identity["tmdb_id"]
        season, episode = identity.get("season"), identity.get("lookup_episode", identity.get("episode"))
        expected_episode_id = None
        try:
            if identity.get("episode_group") and kind in {"season", "episode"}:
                # Unlike get_tv_group_detail(), this retains original season/episode numbers.
                groups = client.tv.group_episodes(identity["episode_group"])
                group = next((g for g in groups or [] if g.get("order") == season), None)
                if not group: raise TranslationError("identity_unknown", "分集组映射无法确认")
                episodes = group.get("episodes") or []
                if kind == "episode":
                    if not isinstance(episode, int) or episode < 1 or episode > len(episodes):
                        raise TranslationError("identity_unknown", "分集组集号无法确认")
                    source = episodes[episode - 1]
                    season, episode, expected_episode_id = source.get("season_number"), source.get("episode_number"), source.get("id")
                    if season is None or episode is None or not expected_episode_id:
                        raise TranslationError("identity_unknown", "分集组缺少原始季集身份")
                else:
                    # An arbitrary group can span seasons; it has no season-translations identity.
                    seasons = {e.get("season_number") for e in episodes}
                    if len(seasons) != 1 or None in seasons:
                        raise TranslationError("identity_unknown", "此分组跨越原始季，无法确定季译文来源")
                    season = next(iter(seasons))
                    official = client.season_obj.details(media_id, season, append_to_response="translations")
                    if {e.get("id") for e in episodes} != {e.get("id") for e in (official or {}).get("episodes", [])}:
                        raise TranslationError("identity_unknown", "此分组不等同完整原始季，保留本地内容")
            if kind == "movie": data = client.movie.details(media_id, append_to_response="translations")
            elif kind == "tv": data = client.tv.details(media_id, append_to_response="translations")
            elif kind == "season": data = client.season_obj.details(media_id, season, append_to_response="translations")
            else: data = client.episode_obj.details(media_id, season, episode, append_to_response="translations")
            if not isinstance(data, dict) or not data.get("id") or data.get("success") is False:
                raise TranslationError("source_unavailable", "TMDB 未返回有效详情，未记为无原文", True)
            if kind in {"movie", "tv"} and int(data["id"]) != int(media_id):
                raise TranslationError("identity_unknown", "TMDB 返回身份不一致")
            if expected_episode_id and data["id"] != expected_episode_id:
                raise TranslationError("identity_unknown", "分集组与原始单集身份不一致")
            translations = data.get("translations", {}).get("translations")
            if not isinstance(translations, list):
                raise TranslationError("source_unavailable", "TMDB 翻译查询不完整", True)
            values = {}
            for record in translations:
                language = record.get("iso_639_1", "")
                if not language: continue
                country = record.get("iso_3166_1", "")
                language = locale(language + ("-" + country if country else ""))
                raw = record.get("data") or {}
                title = raw.get("title") if kind == "movie" else raw.get("name")
                values[language] = {"title": title or "", "overview": raw.get("overview") or "", "tagline": raw.get("tagline") or ""}
            original = data.get("original_language") or identity.get("original_language")
            original_title = data.get("original_title") or data.get("original_name")
            if original and original_title:
                values.setdefault(locale(original), {}).setdefault("title", original_title)
                if not values[locale(original)].get("title"): values[locale(original)]["title"] = original_title
            return {"identity": {**identity, "source_season": season, "source_episode": episode, "entity_id": data["id"]},
                    "translations": values, "original_language": locale(original) if original else "", "supported_fields": ["title", "plot", "outline"] + (["tagline"] if kind in {"movie", "tv"} else [])}
        except TranslationError: raise
        except Exception:
            raise TranslationError("source_unavailable", "TMDB 语言查询失败", True) from None


def value_at(snapshot, language, field):
    language = locale(language)
    values = snapshot["translations"]
    key = FIELD_SOURCE[field]
    candidates = [language]
    # Chinese scripts must never be silently merged. Other regional fallback is explicit.
    if not language.startswith("zh"):
        candidates += sorted(k for k in values if k.split("-")[0] == language.split("-")[0] and k != language)
    for candidate in candidates:
        value = (values.get(candidate, {}).get(key) or "").strip()
        if value and not (field == "title" and placeholder(value)):
            return value, candidate
    return "", language
