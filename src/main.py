import logging
import pathway as pw


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    with open("./examples/el_pipeline.yaml") as f:
        config = pw.load_yaml(f)
        persistence_config = config.get("persistence_config")
        pw.run(persistence_config=persistence_config)


if __name__ == "__main__":
    main()
