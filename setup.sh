#!/bin/bash
#This code was published by @MightyAyush on github.com/mightyayush

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}==================================================${NC}"
echo -e "${GREEN}        BioLinkRemover VPS Setup Script           ${NC}"
echo -e "${CYAN}==================================================${NC}"

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo -e "System detected: Linux"
else
    echo -e "${YELLOW}Warning: This script is intended for Linux VPS environments (Ubuntu/Debian). Proceeding...${NC}"
fi

echo -e "\n${CYAN}[Step 1/4] Installing system dependencies...${NC}"
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

echo -e "\n${CYAN}[Step 2/4] Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}Virtual environment 'venv' created.${NC}"
else
    echo -e "Virtual environment 'venv' already exists."
fi

echo -e "\n${CYAN}[Step 3/4] Installing python packages...${NC}"
source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}All dependencies installed successfully.${NC}"
else
    echo -e "${RED}Error: requirements.txt not found!${NC}"
fi

echo -e "\n${CYAN}[Step 4/4] Configuring environment variables (.env)...${NC}"

if [ -f ".env" ]; then
    echo -e "${YELLOW}An existing .env file was found. Loading current configuration...${NC}"
    source .env 2>/dev/null
fi

prompt_value() {
    local var_name=$1
    local prompt_text=$2
    local current_val=${!var_name}
    
    current_val=$(echo "$current_val" | sed -e 's/^"//' -e 's/"$//')
    
    if [ -n "$current_val" ]; then
        read -p "$(echo -e "${GREEN}$prompt_text [Current: $current_val]: ${NC}")" new_val
        if [ -z "$new_val" ]; then
            eval "$var_name=\"$current_val\""
        else
            eval "$var_name=\"$new_val\""
        fi
    else
        read -p "$(echo -e "${GREEN}$prompt_text: ${NC}")" new_val
        eval "$var_name=\"$new_val\""
    fi
}

prompt_value OWNER_ID "Enter Bot Owner Telegram ID (e.g. 7467775243)"
prompt_value API_ID "Enter Telegram API ID (from my.telegram.org)"
prompt_value API_HASH "Enter Telegram API HASH"
prompt_value BOT_TOKEN "Enter Telegram Bot Token (from @BotFather)"
prompt_value MONGO_DB "Enter MongoDB Connection String"
prompt_value MONGODB_DB_NAME "Enter MongoDB Database Name (e.g. Testing)"
prompt_value LOGGER_GROUP "Enter Logger Group Chat ID (e.g. -100xxxxxxxxxx)"
prompt_value DATABASE_CHANNEL "Enter Database Channel ID (e.g. -100xxxxxxxxxx)"
prompt_value SUDO_USERS "Enter Sudo User IDs (comma-separated list, e.g. 123456,789101 or leave empty)"

cat <<EOF > .env
OWNER_ID = $OWNER_ID
API_ID = $API_ID
API_HASH = "$API_HASH"
BOT_TOKEN = "$BOT_TOKEN"
MONGO_DB = "$MONGO_DB"
MONGODB_DB_NAME = "$MONGODB_DB_NAME"
LOGGER_GROUP = $LOGGER_GROUP
DATABASE_CHANNEL = $DATABASE_CHANNEL
SUDO_USERS = [$SUDO_USERS]
EOF

echo -e "\n${GREEN}Configuration successfully written to .env file!${NC}"

echo -e "\n${CYAN}==================================================${NC}"
echo -e "${GREEN}             Setup Completed!                     ${NC}"
echo -e "${CYAN}==================================================${NC}"
echo -e "You can run the bot manually using:"
echo -e "  ${YELLOW}source venv/bin/activate && python3 main.py${NC}"
echo -e ""
echo -e "Would you like to register this bot as a Systemd service to run in the background? (y/n)"
read -p "Answer: " register_service

if [[ "$register_service" == "y" || "$register_service" == "Y" ]]; then
    SERVICE_PATH="/etc/systemd/system/biolink.service"
    WORKING_DIR=$(pwd)
    
    echo -e "\nCreating systemd service file..."
    
    sudo bash -c "cat <<EOF > $SERVICE_PATH
[Unit]
Description=BioLinkRemover Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=$WORKING_DIR
ExecStart=$WORKING_DIR/venv/bin/python3 $WORKING_DIR/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF"

    sudo systemctl daemon-reload
    sudo systemctl enable biolink.service
    sudo systemctl start biolink.service
    
    echo -e "${GREEN}Systemd service 'biolink' registered and started!${NC}"
    echo -e "Manage the bot using:"
    echo -e "  - Start:   ${YELLOW}sudo systemctl start biolink${NC}"
    echo -e "  - Stop:    ${YELLOW}sudo systemctl stop biolink${NC}"
    echo -e "  - Status:  ${YELLOW}sudo systemctl status biolink${NC}"
    echo -e "  - Logs:    ${YELLOW}sudo journalctl -u biolink -f${NC}"
fi

echo -e "\n${GREEN}Have fun using BioLinkRemover bot!${NC}\n"
