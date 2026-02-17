# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory to /app inside the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose port 5000 to the host machine
EXPOSE 8080

# Define the command to run the Flask app when the container starts
# CMD ["python", "app.py"]

# ... other Dockerfile instructions
#CMD ["flask", "run", "--port", "8080", "--host", "0.0.0.0"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]

