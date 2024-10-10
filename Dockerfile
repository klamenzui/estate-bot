FROM python:3.12-alpine

LABEL authors="klame"

# Set the working directory
WORKDIR /app

# Install Git
RUN apk add --no-cache git

# Clone the GitHub repository
RUN git clone https://github.com/klamenzui/estate-bot.git /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

VOLUME /app/src

# Run the script
CMD ["python", "src/bot.py"]
