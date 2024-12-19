#!/bin/bash
# run.sh

# Default values
REBUILD=false
DETACH=true  # Default to detached mode

# Colors for better visibility
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if sudo is needed for docker
needs_sudo() {
    if docker info >/dev/null 2>&1; then
        return 1  # No sudo needed
    else
        if sudo docker info >/dev/null 2>&1; then
            return 0  # Sudo needed and works
        else
            echo -e "${RED}Error: Cannot connect to Docker daemon even with sudo.${NC}"
            echo "Please check Docker installation and permissions."
            exit 1
        fi
    fi
}

# Function to check if docker daemon is running
check_docker() {
    if ! sudo docker info >/dev/null 2>&1; then
        echo -e "${RED}Error: Docker daemon is not running.${NC}"
        echo "Please start Docker Desktop or the Docker service first."
        exit 1
    fi
}

# Function to run docker compose with or without sudo
docker_compose() {
    if needs_sudo; then
        echo -e "${YELLOW}Running docker compose with sudo${NC}"
        sudo docker compose "$@"
    else
        docker compose "$@"
    fi
}

# Function to stop running containers
stop_running_containers() {
    echo -e "${YELLOW}Stopping any running containers...${NC}"
    docker_compose --profile dev down --remove-orphans 2>/dev/null
    docker_compose --profile prod down --remove-orphans 2>/dev/null
    docker_compose --profile test down --remove-orphans 2>/dev/null
    echo -e "${GREEN}Containers stopped.${NC}"
}

# Function to display header
show_header() {
    clear
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}   MarkItDown Service Manager${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
    # Show if running with sudo
    if needs_sudo; then
        echo -e "${YELLOW}Running with sudo (docker group membership not detected)${NC}"
        echo
    fi
}

# Function to display usage
usage() {
    echo -e "${YELLOW}Usage: $0 [OPTIONS] {dev|prod|test}${NC}"
    echo
    echo "Options:"
    echo "  -r, --rebuild    Force rebuild of Docker images"
    echo "  -d, --detach     Run containers in detached mode (default: true)"
    echo "  -f, --foreground Run containers in foreground"
    echo "  -h, --help       Display this help message"
    echo
    echo "Environments:"
    echo "  dev     Development environment with hot reload"
    echo "  prod    Production environment"
    echo "  test    Test environment"
}

# Function to select environment
select_environment() {
    show_header
    echo -e "${GREEN}Select Environment:${NC}"
    echo "1) Development (with hot reload)"
    echo "2) Production"
    echo "3) Test"
    echo "4) Exit"
    echo
    read -p "Enter choice [1-4]: " choice

    case $choice in
        1) ENVIRONMENT="dev" ;;
        2) ENVIRONMENT="prod" ;;
        3) ENVIRONMENT="test" ;;
        4) exit 0 ;;
        *) 
            echo -e "${RED}Invalid choice${NC}"
            sleep 2
            select_environment
            ;;
    esac
}

# Function to select options
select_options() {
    show_header
    echo -e "${GREEN}Current Configuration:${NC}"
    echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"
    echo -e "Rebuild: ${YELLOW}$REBUILD${NC}"
    echo -e "Detached Mode: ${YELLOW}$DETACH${NC}"
    echo
    echo "Select Options:"
    echo "1) Set Rebuild (Currently: ${REBUILD})"
    echo "2) Set Detached Mode (Currently: ${DETACH})"
    echo "3) Continue with current settings"
    echo "4) Go back to environment selection"
    echo "5) Exit"
    echo
    read -p "Enter choice [1-5]: " choice

    case $choice in
        1) 
            read -p "Enable rebuild? (y/n): " rebuild_choice
            case $rebuild_choice in
                [yY]|[yY][eE][sS]) REBUILD=true ;;
                [nN]|[nN][oO]) REBUILD=false ;;
                *) 
                    echo -e "${RED}Invalid choice${NC}"
                    sleep 2
                    ;;
            esac
            select_options
            ;;
        2) 
            read -p "Enable detached mode? (y/n): " detach_choice
            case $detach_choice in
                [yY]|[yY][eE][sS]) DETACH=true ;;
                [nN]|[nN][oO]) DETACH=false ;;
                *) 
                    echo -e "${RED}Invalid choice${NC}"
                    sleep 2
                    ;;
            esac
            select_options
            ;;
        3) return ;;
        4) 
            select_environment
            select_options
            ;;
        5) exit 0 ;;
        *) 
            echo -e "${RED}Invalid choice${NC}"
            sleep 2
            select_options
            ;;
    esac
}

# Function to confirm settings
confirm_settings() {
    show_header
    echo -e "${GREEN}Please confirm your settings:${NC}"
    echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"
    echo -e "Rebuild Images: ${YELLOW}$REBUILD${NC}"
    echo -e "Detached Mode: ${YELLOW}$DETACH${NC}"
    echo
    echo -e "${YELLOW}Note: Starting this environment will stop any other running containers${NC}"
    echo
    read -p "Proceed with these settings? (y/n): " confirm
    case $confirm in
        [yY]|[yY][eE][sS]) return ;;
        [nN]|[nN][oO]) 
            select_options
            confirm_settings
            ;;
        *) 
            echo -e "${RED}Invalid choice${NC}"
            sleep 2
            confirm_settings
            ;;
    esac
}

# Function to handle cleanup on script exit
cleanup() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}An error occurred. Cleaning up...${NC}"
        stop_running_containers
    fi
}

# Main execution
main() {
    trap cleanup EXIT
    
    # Check if Docker is running first
    check_docker

    # Check if command line arguments were provided
    if [ $# -gt 0 ]; then
        # Process command line arguments
        while [[ $# -gt 0 ]]; do
            case "$1" in
                -r|--rebuild)
                    REBUILD=true
                    shift
                    ;;
                -d|--detach)
                    DETACH=true
                    shift
                    ;;
                -f|--foreground)
                    DETACH=false
                    shift
                    ;;
                -h|--help)
                    usage
                    exit 0
                    ;;
                dev|prod|test)
                    ENVIRONMENT=$1
                    shift
                    ;;
                *)
                    echo -e "${RED}Error: Unknown option $1${NC}"
                    usage
                    exit 1
                    ;;
            esac
        done
    else
        # Interactive mode
        select_environment
        select_options
        confirm_settings
    fi

    # Execute docker compose
    show_header
    
    # Stop any running containers first
    stop_running_containers

    case "$ENVIRONMENT" in
        dev)
            echo -e "${GREEN}Starting development environment...${NC}"
            if [ "$REBUILD" = true ]; then
                docker_compose --profile $ENVIRONMENT build markitdown-dev
            fi
            if [ "$DETACH" = true ]; then
                docker_compose --profile $ENVIRONMENT up -d --remove-orphans markitdown-dev
            else
                docker_compose --profile $ENVIRONMENT up --remove-orphans markitdown-dev
            fi
            ;;
        prod)
            echo -e "${GREEN}Starting production environment...${NC}"
            if [ "$REBUILD" = true ]; then
                docker_compose --profile $ENVIRONMENT build markitdown-prod
            fi
            if [ "$DETACH" = true ]; then
                docker_compose --profile $ENVIRONMENT up -d --remove-orphans markitdown-prod
            else
                docker_compose --profile $ENVIRONMENT up --remove-orphans markitdown-prod
            fi
            ;;
        test)
            echo -e "${GREEN}Running tests...${NC}"
            if [ "$REBUILD" = true ]; then
                docker_compose --profile $ENVIRONMENT build markitdown-test
            fi
            if [ "$DETACH" = true ]; then
                docker_compose --profile $ENVIRONMENT up -d --remove-orphans markitdown-test
            else
                docker_compose --profile $ENVIRONMENT up --remove-orphans markitdown-test
            fi
            ;;
    esac
}

# Start the script
main "$@"
