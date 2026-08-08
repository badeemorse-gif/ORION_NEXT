from app.application import OrionApplication, ApplicationConfiguration

def main():
    config = ApplicationConfiguration()

    app = OrionApplication(config)

    print("=" * 60)
    print("ORION SMOKE TEST")
    print("=" * 60)

    app.start()

    print("✓ Application Started")

    print(app.health())

    app.shutdown()

    print("✓ Application Shutdown")

if __name__ == "__main__":
    main()