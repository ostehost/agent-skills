---
diataxis: reference
---

# `weatherctl fetch`

Fetches current conditions for one city and prints them to standard output.

## Synopsis

```text
weatherctl fetch [--units UNITS] [--timeout SECONDS] [--format FORMAT] CITY
```

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--units` | string | `metric` | Unit system: `metric` or `imperial`. |
| `--timeout` | integer | `10` | Seconds before the request fails. |
| `--format` | string | `text` | Output format: `text` or `json`. |

## Arguments

`CITY` is a city name or a three-letter airport code. It must not be empty.
Sub-commands are not accepted after `CITY`.

## Exit status

- `0`: the request succeeded and conditions were printed.
- `1`: the city was not found in the catalogue.
- `2`: the arguments were invalid or incomplete.
- `3`: the upstream service did not answer within the timeout.

## Environment

- `WEATHER_TOKEN`: the API token sent with every request.
- `WEATHER_ENDPOINT`: the base URL of the service.

You must set `WEATHER_TOKEN` before calling `fetch`. Never pass the token on
the command line. The timeout must be between 1 and 120 seconds.

## Example

```console
$ weatherctl fetch --units imperial Lisbon
Lisbon: 70°F, clear
```
