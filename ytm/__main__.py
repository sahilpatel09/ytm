from ytm.app import YtmApp


def main() -> None:
    app = YtmApp()
    try:
        app.run()
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()
