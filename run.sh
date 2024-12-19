#!/bin/bash
# run.sh

# Default values
REBUILD=false
DETACH=true  # Default to detached mode
SHOW_LOGS=false
FOLLOW_LOGS=false
CLEAN=false
CLEAN_ALL=false
FORCE=false

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

# Function to show logs
show_logs() {
    local env=${1:-$ENVIRONMENT}  # Use passed environment or current one
    local follow=${2:-false}      # Whether to follow logs
    local service=""

    case "$env" in
        dev)  service="markitdown-dev" ;;
        prod) service="markitdown-prod" ;;
        test) service="markitdown-test" ;;
        *)    
            echo -e "${RED}Invalid environment: $env${NC}"
            return 1
            ;;
    esac

    if [ "$follow" = true ]; then
        echo -e "${GREEN}Showing and following logs for $service...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop following${NC}"
        docker_compose --profile $env logs -f $service
    else
        echo -e "${GREEN}Showing logs for $service...${NC}"
        docker_compose --profile $env logs $service
    fi
}

# Function to stop running containers
stop_running_containers() {
    echo -e "${YELLOW}Stopping any running containers...${NC}"
    docker_compose --profile test down --remove-orphans 2>/dev/null
    docker_compose --profile dev down --remove-orphans 2>/dev/null
    docker_compose --profile prod down --remove-orphans 2>/dev/null
    echo -e "${GREEN}Containers stopped.${NC}"
}

# Function to clean environment
clean_environment() {
    local env=$1
    local force=${2:-false}

    # Extra confirmation for production
    if [ "$env" = "prod" ] && [ "$force" != true ]; then
        echo -e "${RED}WARNING: You are about to completely clean the PRODUCTION environment!${NC}"
        echo -e "${RED}This will delete all data, volumes, and containers.${NC}"
        echo -e "${YELLOW}Type 'CONFIRM-PROD-CLEAN' to proceed:${NC}"
        read -r confirmation
        if [ "$confirmation" != "CONFIRM-PROD-CLEAN" ]; then
            echo -e "${GREEN}Clean operation cancelled.${NC}"
            return 1
        fi
    fi

    echo -e "${YELLOW}Cleaning ${env} environment (including volumes)...${NC}"
    docker_compose --profile test down -v 2>/dev/null
    docker_compose --profile $env down -v
    echo -e "${GREEN}Clean complete for ${env} environment.${NC}"
}

# Function to clean all environments
clean_all() {
    local force=${1:-false}
    
    echo -e "${RED}WARNING: This will clean ALL environments!${NC}"
    if [ "$force" != true ]; then
        echo -e "${YELLOW}Type 'CONFIRM-CLEAN-ALL' to proceed:${NC}"
        read -r confirmation
        if [ "$confirmation" != "CONFIRM-CLEAN-ALL" ]; then
            echo -e "${GREEN}Clean operation cancelled.${NC}"
            return 1
        fi
    fi

    echo -e "${YELLOW}Cleaning all environments...${NC}"
    docker_compose --profile test down -v
    docker_compose --profile dev down -v
    docker_compose --profile prod down -v
    echo -e "${GREEN}All environments cleaned.${NC}"
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
    echo "  -l, --logs       Show logs for the environment"
    echo "  -F, --follow     Show and follow logs for the environment"
    echo "  -c, --clean      Clean environment (delete containers, volumes, etc.)"
    echo "  -C, --clean-all  Clean all environments"
    echo "  --force          Force clean without confirmation (dangerous!)"
    echo "  -h, --help       Display this help message"
    echo
    echo "Environments:"
    echo "  dev     Development environment with hot reload"
    echo "  prod    Production environment"
    echo "  test    Test environment"
    echo
    echo "Examples:"
    echo "  $0 dev              # Start development environment"
    echo "  $0 -r prod         # Rebuild and start production environment"
    echo "  $0 -f test         # Start test environment in foreground"
    echo "  $0 -l dev          # Show development logs"
    echo "  $0 -F prod         # Follow production logs"
    echo "  $0 -c dev          # Clean development environment"
    echo "  $0 -C              # Clean all environments"
    echo "  $0 -c prod         # Clean production (requires confirmation)"
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
                -l|--logs)
                    SHOW_LOGS=true
                    shift
                    ;;
                -F|--follow)
                    SHOW_LOGS=true
                    FOLLOW_LOGS=true
                    shift
                    ;;
                -c|--clean)
                    CLEAN=true
                    shift
                    ;;
                -C|--clean-all)
                    CLEAN_ALL=true
                    shift
                    ;;
                --force)
                    FORCE=true
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

        # Handle cleaning operations
        if [ "$CLEAN_ALL" = true ]; then
            clean_all $FORCE
            exit 0
        fi

        if [ "$CLEAN" = true ]; then
            if [ -z "$ENVIRONMENT" ]; then
                echo -e "${RED}Error: Environment must be specified for clean operation${NC}"
                exit 1
            fi
            clean_environment $ENVIRONMENT $FORCE
            exit 0
        fi

        # If showing logs, do that and exit
        if [ "$SHOW_LOGS" = true ]; then
            show_logs "$ENVIRONMENT" "$FOLLOW_LOGS"
            exit 0
        fi
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

    # If we started in detached mode, show how to view logs
    if [ "$DETACH" = true ]; then
        echo -e "\n${GREEN}Container started in detached mode.${NC}"
        echo -e "To view logs, run: ${YELLOW}$0 -l $ENVIRONMENT${NC}"
        echo -e "To follow logs, run: ${YELLOW}$0 -F $ENVIRONMENT${NC}"
    fi
}

# Start the script
main "$@"
