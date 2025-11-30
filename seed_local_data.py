from elections.management.commands.seed_demo_data import Command as SeedCommand

if __name__ == "__main__":
    # Allow running with `python seed_local_data.py` for quick local setup
    SeedCommand().handle()
