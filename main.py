def main():
    try:
        from ui import PythonBrowserApp
    except Exception as exc:
        print(exc)
        raise SystemExit(1)

    app = PythonBrowserApp()
    app.run(None)


if __name__ == "__main__":
    main()
