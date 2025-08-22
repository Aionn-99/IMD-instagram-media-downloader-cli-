import argparse
from instagram_downloader import InstagramDownloader

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username", help="Instagram username")
    parser.add_argument(
        "--max-items", "-m",
        type=int, default=None,
        help="Maksimum media yang ingin diunduh (kosongkan untuk semua)"
    )
    parser.add_argument(
        "--per-page", "-p",
        type=int, default=12,
        help="Jumlah item per halaman permintaan (default: 12)"
    )
    args = parser.parse_args()
    InstagramDownloader(args.username).run(
        max_items=args.max_items,
        per_page=args.per_page
    )

if __name__=="__main__":
    main()