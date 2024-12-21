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
declare -A COLORS=(
    ["RED"]='\033[0;31m'
    ["GREEN"]='\033[0;32m'
    ["YELLOW"]='\033[1;33m'
    ["BLUE"]='\033[0;34m'
    ["NC"]='\033[0m'
)

# Environment configurations
declare -A ENV_CONFIGS=(
    ["dev"]="markitdown-dev"
    ["prod"]="markitdown-prod"
    ["test"]="markitdown-test"
)

# Function to print colored message
print_colored() {
    local color="${COLORS[$1]}"
    local message="$2"
    echo -e "${color}${message}${COLORS[NC]}"
}

# Function to check if sudo is needed for docker
needs_sudo() {
    if docker info >/dev/null 2>&1; then
        return 1  # No sudo needed
    elif sudo docker info >/dev/null 2>&1; then
        return 0  # Sudo needed and works
    else
        print_colored "RED" "Error: Cannot connect to Docker daemon even with sudo."
        echo "Please check Docker installation and permissions."
        exit 1
    fi
}

# Function to check if docker daemon is running
check_docker() {
    if ! sudo docker info >/dev/null 2>&1; then
        print_colored "RED" "Error: Docker daemon is not running."
        echo "Please start Docker Desktop or the Docker service first."
        exit 1
    fi
}

# Function to run docker compose with or without sudo
docker_compose() {
    if needs_sudo; then
        print_colored "YELLOW" "Running docker compose with sudo"
        sudo docker compose "$@"
    else
        docker compose "$@"
    fi
}

# Function to show logs
show_logs() {
    local env=${1:-$ENVIRONMENT}
    local follow=${2:-false}
    local service="${ENV_CONFIGS[$env]}"

    if [ -z "$service" ]; then
        print_colored "RED" "Invalid environment: $env"
        return 1
    fi

    if [ "$follow" = true ]; then
        print_colored "GREEN" "Showing and following logs for $service..."
        print_colored "YELLOW" "Press Ctrl+C to stop following"
        docker_compose --profile $env logs -f $service
    else
        print_colored "GREEN" "Showing logs for $service..."
        docker_compose --profile $env logs $service
    fi
}

# Function to stop running containers
stop_running_containers() {
    print_colored "YELLOW" "Stopping any running containers..."
    for env in "${!ENV_CONFIGS[@]}"; do
        docker_compose --profile $env down --remove-orphans 2>/dev/null
    done
    print_colored "GREEN" "Containers stopped."
}

# Function to clean environment
clean_environment() {
    local env=$1
    local force=${2:-false}
    local service="${ENV_CONFIGS[$env]}"

    if [ -z "$service" ]; then
        print_colored "RED" "Invalid environment: $env"
        return 1
    fi  # <-- This was the problem (had an extra })

    # Extra confirmation for production
    if [ "$env" = "prod" ] && [ "$force" != true ]; then
        print_colored "RED" "WARNING: You are about to completely clean the PRODUCTION environment!"
        print_colored "RED" "This will delete all data, volumes, and containers."
        print_colored "YELLOW" "Type 'CONFIRM-PROD-CLEAN' to proceed:"
        read -r confirmation
        if [ "$confirmation" != "CONFIRM-PROD-CLEAN" ]; then
            print_colored "GREEN" "Clean operation cancelled."
            return 1
        fi
    fi

    print_colored "YELLOW" "Cleaning ${env} environment (including volumes)..."
    docker_compose --profile $env down -v
    print_colored "GREEN" "Clean complete for ${env} environment."
}

# Function to clean all environments
clean_all() {
    local force=${1:-false}
    
    print_colored "RED" "WARNING: This will clean ALL environments!"
    if [ "$force" != true ]; then
        print_colored "YELLOW" "Type 'CONFIRM-CLEAN-ALL' to proceed:"
        read -r confirmation
        if [ "$confirmation" != "CONFIRM-CLEAN-ALL" ]; then
            print_colored "GREEN" "Clean operation cancelled."
            return 1
        fi
    fi

    print_colored "YELLOW" "Cleaning all environments..."
    for env in "${!ENV_CONFIGS[@]}"; do
        docker_compose --profile $env down -v
    done
    print_colored "GREEN" "All environments cleaned."
}

# Function to get environment display name and color
get_env_display() {
    local env=$1
    case "$env" in
        dev)  print_colored "GREEN" "DEVELOPMENT" ;;
        prod) print_colored "RED" "PRODUCTION" ;;
        test) print_colored "YELLOW" "TEST" ;;
        *)    print_colored "BLUE" "NONE" ;;
    esac
}

# Function to get running environment
get_running_environment() {
    for env in "${!ENV_CONFIGS[@]}"; do
        if docker_compose ps | grep -q "markitlikeitshot-${ENV_CONFIGS[$env]}-"; then
            echo "$env"
            return
        fi
    done
    echo "none"
}

# Function to display header
show_header() {
    clear
    print_colored "BLUE" "================================"
    print_colored "BLUE" "   MarkItDown Service Manager"
    print_colored "BLUE" "================================"
    
    local running_env=$(get_running_environment)
    
    echo -e "\nRunning Environment: $(get_env_display "$running_env")"
    
    if [ -n "$ENVIRONMENT" ]; then
        echo -e "Selected Environment: $(get_env_display "$ENVIRONMENT")"
    fi
    
    echo
    if needs_sudo; then
        print_colored "YELLOW" "Running with sudo (docker group membership not detected)"
        echo
    fi
}

# Function to display usage
usage() {
    print_colored "YELLOW" "Usage: $0 [OPTIONS] {dev|prod|test}"
    cat << EOF

Options:
  -r, --rebuild    Force rebuild of Docker images
  -d, --detach     Run containers in detached mode (default: true)
  -f, --foreground Run containers in foreground
  -l, --logs       Show logs for the environment
  -F, --follow     Show and follow logs for the environment
  -c, --clean      Clean environment (delete containers, volumes, etc.)
  -C, --clean-all  Clean all environments
  --force          Force clean without confirmation (dangerous!)
  -h, --help       Display this help message

Environments:
  dev     Development environment with hot reload
  prod    Production environment
  test    Test environment

Examples:
  $0 dev              # Start development environment
  $0 -r prod         # Rebuild and start production environment
  $0 -f test         # Start test environment in foreground
  $0 -l dev          # Show development logs
  $0 -F prod         # Follow production logs
  $0 -c dev          # Clean development environment
  $0 -C              # Clean all environments
  $0 -c prod         # Clean production (requires confirmation)
EOF
}

# Function to select environment
select_environment() {
    show_header
    print_colored "GREEN" "Select Environment:"
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
            print_colored "RED" "Invalid choice"
            sleep 2
            select_environment
            ;;
    esac
}

# Function to select options
select_options() {
    show_header
    print_colored "GREEN" "Current Configuration:"
    echo -e "Environment: $(get_env_display "$ENVIRONMENT")"
    echo -e "Rebuild: ${COLORS[YELLOW]}$REBUILD${COLORS[NC]}"
    echo -e "Detached Mode: ${COLORS[YELLOW]}$DETACH${COLORS[NC]}"
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
                    print_colored "RED" "Invalid choice"
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
                    print_colored "RED" "Invalid choice"
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
            print_colored "RED" "Invalid choice"
            sleep 2
            select_options
            ;;
    esac
}

# Function to start environment
start_environment() {
    local env=$1
    local service="${ENV_CONFIGS[$env]}"
    
    print_colored "GREEN" "Starting $(get_env_display "$env") environment..."
    
    if [ "$REBUILD" = true ]; then
        docker_compose --profile $env build $service
    fi
    
    # Special handling for test environment
    if [ "$env" = "test" ]; then
        print_colored "YELLOW" "Running tests..."
        
        # Run tests and capture exit code
        if docker_compose --profile test run --rm $service; then
            print_colored "GREEN" "Tests completed successfully!"
        else
            print_colored "RED" "Tests failed!"
            exit 1
        fi
        
        # Clean up test environment
        print_colored "YELLOW" "Cleaning up test environment..."
        docker_compose --profile test down -v
        print_colored "GREEN" "Test environment cleaned up"
        
        return
    fi
    
    # Normal environment startup for non-test environments
    if [ "$DETACH" = true ]; then
        docker_compose --profile $env up -d --remove-orphans $service
    else
        docker_compose --profile $env up --remove-orphans $service
    fi
}

# Function to handle cleanup on script exit
cleanup() {
    if [ $? -ne 0 ]; then
        print_colored "RED" "An error occurred. Cleaning up..."
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
                    print_colored "RED" "Error: Unknown option $1"
                    usage
                    exit 1
                    ;;
            esac
        done

        if [ "$CLEAN_ALL" = true ]; then
            clean_all $FORCE
            exit 0
        fi

        if [ "$CLEAN" = true ]; then
            if [ -z "$ENVIRONMENT" ]; then
                print_colored "RED" "Error: Environment must be specified for clean operation"
                exit 1
            fi
            clean_environment $ENVIRONMENT $FORCE
            exit 0
        fi

        if [ "$SHOW_LOGS" = true ]; then
            show_logs "$ENVIRONMENT" "$FOLLOW_LOGS"
            exit 0
        fi
    else
        # Interactive mode
        select_environment
        select_options
    fi

    # Execute docker compose
    show_header
    stop_running_containers
    start_environment "$ENVIRONMENT"

    # If we started in detached mode, show how to view logs
    if [ "$DETACH" = true ]; then
        echo
        print_colored "GREEN" "Container started in detached mode."
        print_colored "YELLOW" "To view logs, run: $0 -l $ENVIRONMENT"
        print_colored "YELLOW" "To follow logs, run: $0 -F $ENVIRONMENT"
    fi
}

# Start the script
main "$@"