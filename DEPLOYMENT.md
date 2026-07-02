# Deployment Guide: Render & Railway

This guide explains how to host your **InkBit LMS** on Render or Railway with persistent storage so your SQLite database and uploaded files are saved permanently.

---

## 1. Prerequisites
* A GitHub repository containing this project.
* A free account on [Render](https://render.com/) or [Railway](https://railway.app/).

---

## 2. Deploying on Render (Recommended)

Render is extremely simple and supports free/low-cost Web Services with persistent disks.

### Step 1: Create a Web Service
1. Log in to Render and click **New > Web Service**.
2. Connect your GitHub repository.
3. Configure the following settings:
   * **Name:** `inkbit-lms`
   * **Region:** Choose the region closest to your users.
   * **Branch:** `main` (or your default branch)
   * **Runtime:** `Python`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn app:app`
   * **Instance Type:** Choose the **Free** or **Starter** tier.

### Step 2: Attach a Persistent Disk (Crucial!)
Since Render's file system is temporary, we must mount a persistent disk to hold your SQLite database (`inkbit.db`) and student uploads (`uploads/`).
1. In your Web Service settings, scroll down to the **Disks** section and click **Add Disk**.
2. Enter the following details:
   * **Name:** `inkbit-storage`
   * **Mount Path:** `/data`
   * **Size:** `1 GB` (more than enough to start)
3. Click **Save**.

### Step 3: Configure Environment Variables
Go to the **Environment** tab of your Web Service and add the following keys:
* `DATABASE_URL` = `sqlite:////data/inkbit.db` *(Note the 4 slashes! This stores the database on your persistent disk)*
* `UPLOAD_FOLDER` = `/data/uploads` *(This stores uploaded files on the persistent disk)*
* `SECRET_KEY` = `your-custom-secure-random-string`
* `TELEGRAM_BOT_TOKEN` = `8887475789:AAFw5qWugkO5m-1AStPSNCklRLrv7wU35ZA`

Click **Deploy**! Render will build your application, attach the disk, and launch the LMS.

---

## 3. Deploying on Railway

Railway supports automatic deployment and persistent volumes.

### Step 1: Create a New Project
1. Log in to Railway and click **New Project > Deploy from GitHub repo**.
2. Select your repository.
3. Click **Deploy Now**. (It will deploy, but we need to configure the disk next).

### Step 2: Add a Volume (Persistent Disk)
1. In your project canvas, click your web service block.
2. Go to the **Settings** tab, scroll down to **Volumes**, and click **Add Volume**.
3. Set the Mount Path to `/data`.

### Step 3: Add Variables
Go to the **Variables** tab of your service and add:
* `PORT` = `5000`
* `DATABASE_URL` = `sqlite:////data/inkbit.db`
* `UPLOAD_FOLDER` = `/data/uploads`
* `SECRET_KEY` = `your-custom-secure-random-string`
* `TELEGRAM_BOT_TOKEN` = `8887475789:AAFw5qWugkO5m-1AStPSNCklRLrv7wU35ZA`

Railway will automatically redeploy the application with the volume mounted.
