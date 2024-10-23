FROM python:3.12-alpine

LABEL authors="klame"

# Set the working directory
WORKDIR /app

# Install Git in the container
RUN apk add --no-cache git

# Clone the GitHub repository (This happens only during the build phase)
RUN git clone https://github.com/klamenzui/estate-bot.git /app

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Create a volume to persist data (like your estates.json)
VOLUME /app/src

# Run the Python script
CMD ["python", "src/bot.py"]
