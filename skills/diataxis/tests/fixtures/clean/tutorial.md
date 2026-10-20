---
diataxis: tutorial
---

# Build your first weather dashboard

In this tutorial, we will build a small dashboard that prints the current
temperature for one city. By the end, you will have a script running on your
own machine that refreshes every minute.

You need Python 3.11 and a terminal. Nothing else is required.

## Create the project

First, we make a folder for the project and move into it:

```console
$ mkdir weather && cd weather
```

Now we add the starter file. Create `app.py` with one line:

```python
print("dashboard ready")
```

## Run the dashboard

Let's start it:

```console
$ python3 app.py
dashboard ready
```

You should see the line `dashboard ready` in the terminal. Notice that nothing
else prints yet; the dashboard stays quiet until we give it a city.

## Add a city

Open `app.py` again and replace the print line with a call that names Lisbon.
Then we run the file once more. The output should look like this:

```text
Lisbon: 21°C
```

## What you have built

You have built a working dashboard that reports a live temperature for Lisbon.
Each run asks the weather service for fresh data and prints one line.
