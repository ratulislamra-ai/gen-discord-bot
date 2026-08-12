import asyncio
import logging
from main import main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("GENEsportsBot").info("Bot execution interrupted by user. Shutting down gracefully.")
    except Exception as e:
        logging.getLogger("GENEsportsBot").critical(f"Fatal error while launching bot: {e}")
