import json
from pathlib import Path
import requests
from urllib.parse import urlparse

class InstagramDownloader:
    def __init__(self, username: str):
        self.username = username.strip()
        self.safe_username = "".join(c for c in self.username if c.isalnum() or c in  ("_", "-",".")).strip("._-")
        self.response_dir = Path("response")
        self.urls_dir = Path("urls")
        self.downloads_dir = Path("downloads") / self.safe_username

        self.response_dir.mkdir(parents=True, exist_ok=True)
        self.urls_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        self.response_json = self.response_dir / f"response_{self.safe_username}.json"
        self.response_html = self.response_dir / f"response_{self.safe_username}.html"
        # split outputs
        self.urls_images_txt = self.urls_dir / f"links_images_1080_{self.safe_username}.txt"
        self.urls_videos_txt = self.urls_dir / f"links_videos_{self.safe_username}.txt"

        # subfolders for images and videos
        self.images_dir = self.downloads_dir / "images"
        self.videos_dir = self.downloads_dir / "videos"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)

        self.graphql_url = "https://www.instagram.com/graphql/query"
        try:
            from auth import build_session_and_headers
            self.session, self.headers = build_session_and_headers(self.username)
        except Exception as e:
            self.session = requests.Session()
            self.headers =  {
                "authority": "www.instagram.com",
                "accept": "*/*",
                "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "content-type": "application/x-www-form-urlencoded",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                "x-fb-friendly-name": "PolarisProfilePostsQuery",
            }

    def _variables(self, after: str | None = None, count: int = 12):
        vars_ = {
            "data": {
                "count": count,
                "include_reel_media_seen_timestamp": True,
                "include_relationship_info": True,
                "latest_besties_reel_media": True,
                "latest_reel_media": True,
            },
            "username": self.username,
            "__relay_internal__pv__PolarisIsLoggedInrelayprovider": True,
        }
        # Most Polaris queries accept "after" cursor at top-level variables
        if after:
            vars_["after"] = after
        return vars_

    def fetch_response(self, after: str | None = None, count: int = 12) -> dict | None:
        payload = {
            "variables": json.dumps(self._variables(after=after, count=count), separators=(",", ":")),
            "server_timestamps": "true",
            "doc_id": "9926142507487500",
        }
        resp = self.session.post(self.graphql_url, headers=self.headers, data=payload)
        if resp.status_code != 200:
            print(f"Request failed: {resp.status_code} - {resp.text[:200]}")
            try:
                ck_keys = list(self.session.cookies.get_dict().keys())
                print(f"Cookie keys loaded: {ck_keys}")
                print(f"Has x-csrftoken header: {'x-csrftoken' in self.headers}")
                print(f"Referer header: {self.headers.get('referer')}")
            except Exception:
                pass
            return None
        try:
            self.response_html.write_text(resp.text, encoding="utf-8")
        except Exception:
            pass
        try:
            data = resp.json()
            self.response_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
        except Exception as e:
            print(f"Failed to parse JSON: {e}")
            return None

    def _iter_carousel_media(self, obj):
        if isinstance(obj, dict):
            for k, v  in obj.items():
                if k == "carousel_media" and isinstance(v, list):
                    for m  in v:
                        yield m 
                else:
                    yield from self._iter_carousel_media(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._iter_carousel_media(item)

    def _iter_media_nodes(self, obj):
        if isinstance(obj, dict):
            has_media = ("image_versions2" in obj) or ("video_versions" in obj)
            if has_media:
                yield obj
            for v in obj.values():
                yield from self._iter_media_nodes(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._iter_media_nodes(item)


    def extract_links(self, data:dict) -> list[str]:
        img_urls = set()
        vid_urls = set()

        for node in self._iter_media_nodes(data):
            iv2 = node.get("image_versions2", {})
            for c in iv2.get("candidates", []):
                w = int(c.get("width", -1))
                h = int(c.get("height", -1))
                if w == 1080 and h == 1080 and "url" in c:
                    img_urls.add(c["url"])

            vvs = node.get("video_versions") or []
            if isinstance(vvs, list) and vvs:
                best = max(vvs, key=lambda x: int(x.get("width", 0)) * int(x.get("height", 0))) if vvs else None
                if best and "url" in best:
                    vid_urls.add(best["url"])

        imgs_sorted = sorted(img_urls)
        vids_sorted = sorted(vid_urls)

        self.urls_images_txt.write_text("\n".join(imgs_sorted) + ("\n" if imgs_sorted else ""), encoding="utf-8")
        self.urls_videos_txt.write_text("\n".join(vids_sorted) + ("\n" if vids_sorted else ""), encoding="utf-8")

        print(f"found {len(imgs_sorted)} image links (1080x1080). Saved to {self.urls_images_txt}")
        print(f"found {len(vids_sorted)} video links. Saved to {self.urls_videos_txt}")

        # return combined list for downloading
        return imgs_sorted + vids_sorted
    
        # New: collect links from a page tanpa menulis file
    def collect_links(self, data: dict) -> tuple[set[str], set[str]]:
        imgs = set()
        vids = set()
        for node in self._iter_media_nodes(data):
            iv2 = node.get("image_versions2", {})
            for c in iv2.get("candidates", []):
                w = int(c.get("width", -1))
                h = int(c.get("height", -1))
                if w == 1080 and h == 1080 and "url" in c:
                    imgs.add(c["url"])

            # Ambil SEMUA url video dari video_versions jika ada
            vvs = node.get("video_versions") or []
            if isinstance(vvs, list) and vvs:
                for v in vvs:
                    u = v.get("url")
                    if u:
                        vids.add(u)

            # Beberapa respons menyediakan single 'video_url'
            single_video_url = node.get("video_url")
            if isinstance(single_video_url, str) and single_video_url:
                vids.add(single_video_url)

        # Fallback: scan semua video_versions di seluruh respons
        for vlist in self._iter_all_video_versions(data):
            if isinstance(vlist, list):
                for v in vlist:
                    u = v.get("url") if isinstance(v, dict) else None
                    if u:
                        vids.add(u)

        # Fallback tambahan: cari kunci 'video_url' di mana pun
        for u in self._iter_all_key_values(data, "video_url"):
            if isinstance(u, str) and u:
                vids.add(u)

        return imgs, vids

    # New: temukan semua field video_versions di mana pun berada
    def _iter_all_video_versions(self, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "video_versions":
                    yield v
                else:
                    yield from self._iter_all_video_versions(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._iter_all_video_versions(item)

    # New: cari semua nilai dari key tertentu di mana pun berada
    def _iter_all_key_values(self, obj, target_key: str):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == target_key:
                    yield v
                else:
                    yield from self._iter_all_key_values(v, target_key)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._iter_all_key_values(item, target_key)


        # New: write combined links into files
    def _write_links_files(self, img_urls: list[str], vid_urls: list[str]) -> None:
        self.urls_images_txt.write_text("\n".join(img_urls) + ("\n" if img_urls else ""), encoding="utf-8")
        self.urls_videos_txt.write_text("\n".join(vid_urls) + ("\n" if vid_urls else ""), encoding="utf-8")
        print(f"found {len(img_urls)} image links (1080x1080). Saved to {self.urls_images_txt}")
        print(f"found {len(vid_urls)} video links. Saved to {self.urls_videos_txt}")

    # New: find page_info anywhere in response
    def _find_page_info(self, obj) -> dict | None:
        if isinstance(obj, dict):
            if {"end_cursor", "has_next_page"}.issubset(obj.keys()):
                return obj
            for v in obj.values():
                res = self._find_page_info(v)
                if res:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = self._find_page_info(item)
                if res:
                    return res
        return None

    
    def _next_file_path(self, ext: str, base_dir: Path) -> Path:

        prefix = self.safe_username
        existing_numbers = []
        for p in base_dir.glob(f"{prefix}*{ext}"):
            name = p.name

            if name == f"{prefix}{ext}":
                existing_numbers.append(0)
            else:
                try:
                    base = name[: -len(ext)]
                    if base.startswith(prefix + "_"):
                        n = int(base.split("_")[-1])
                        existing_numbers.append(n)
                except Exception:
                    pass
        
        n = (max(existing_numbers) + 1) if existing_numbers else 0
        fn = f"{prefix}{'' if n == 0 else f'_{n}'}{ext}"
        return base_dir / fn

    def download_links(self, urls: list[str]) -> int:
        count = 0
        for url in urls:
            ext = Path(urlparse(url).path).suffix.lower()
            r = self.session.get(url, headers=self.headers)
            if r.status_code == 200:
                ctype = (r.headers.get("content-type") or "").lower()
                is_video = ext in {".mp4", ".mov", ".mkv", ".avi", ".webm"} or ctype.startswith("video/")
                target_dir = self.videos_dir if is_video else self.images_dir
                final_ext = ext or (".mp4" if is_video else ".jpg")
                path = self._next_file_path(final_ext, target_dir)
                path.write_bytes(r.content)
                count += 1
                print(f"Downloaded: {url}  -> {path}")
            else:
                print(f"Skip ({r.status_code}): {url}")
        print(f"Total  downloaded: {count}")
        return count

    # New: run with pagination and optional max_items
    def run(self, max_items: int | None = None, per_page: int = 12):
        """
        - If max_items is None: download all media across pages.
        - If max_items is set: stop after collecting at least that many URLs.
        """
        all_imgs: set[str] = set()
        all_vids: set[str] = set()

        after = None
        while True:
            data = self.fetch_response(after=after, count=per_page)
            if not data:
                break

            imgs, vids = self.collect_links(data)
            all_imgs |= imgs
            all_vids |= vids

            # stop early if max_items reached
            if max_items is not None:
                if len(all_imgs) + len(all_vids) >= max_items:
                    break

            pi = self._find_page_info(data)
            has_next = bool(pi and pi.get("has_next_page"))
            end_cursor = pi.get("end_cursor") if pi else None
            if not has_next or not end_cursor:
                break
            after = end_cursor

        # combine and cap by max_items if needed (stable sort)
        imgs_sorted = sorted(all_imgs)
        vids_sorted = sorted(all_vids)
        combined = imgs_sorted + vids_sorted
        if max_items is not None:
            combined = combined[:max_items]

        # write split files from the final capped set
        # keep the split files consistent with what will be downloaded
        capped_imgs = [u for u in combined if u in all_imgs]
        capped_vids = [u for u in combined if u in all_vids]
        self._write_links_files(sorted(capped_imgs), sorted(capped_vids))

        if not combined:
            print("No links to download.")
            return

        self.download_links(combined)