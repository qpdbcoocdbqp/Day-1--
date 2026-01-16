# Day-1--
Streaming EL exploration. Playing with [Day 1 ◑](https://www.youtube.com/watch?v=hWOB5QYcmh0).

* **About Day 1 ◑**

> Day 1 ·HONNE
>
> Love Me / Love Me Not

## Reference

* [pathwaycom/pathway](https://github.com/pathwaycom/pathway)

## Exploration


* **Setup**

    ```sh
    uv venv --python 3.13

    uv pip install pathway --extra-index-url https://github.com/pathwaycom/pathway/releases/download/v0.27.0/pathway-0.27.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

    source .venv/bin/activate
    ```

* **Pipeline**

  * [Pipeline](examples/el_pipeline.yaml)
  * convert `json` to `csv`

    ```sh
    # start `el_pipeline`
    python -m src.main
    ```

* **Data Source**

    ```sh
    # generate streaming input, 2 samples per second and duration time is 10 seconds.
    python -m src.input_generate --mode stream --rate 2 --duration 10

    # generate batch input, write 100 files or duration time is 5 seconds.
    python -m src.input_generate --mode batch --files 100 --duration 5

    # generate streaming input, 400 samples per second and duration time is 30 seconds.
    python -m src.input_generate --mode stream --rate 400 --duration 30

    # generate batch input, write 1000 files or duration time is 30 seconds.
    python -m src.input_generate --mode batch --files 1000 --duration 30
    ```