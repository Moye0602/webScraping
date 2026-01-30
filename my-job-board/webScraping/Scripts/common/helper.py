from termcolor import colored

def cprint(*args, color="yellow"):
    """
    Prints colored text to the console.
    *args: The message(s) to print.
    color: The name or index of the color.
    """
    # 1. Join all positional arguments into a single string
    message = " ".join(map(str, args))
    
    # 2. Use the 'colored' library to wrap the text
    # This uses the modern colored.fore(color) + message + style.RESET approach
    print(f"{colored(message, color)}")

#################################
###
#################################
if __name__ == "__main__":
    cprint("Status:", "OK", color="cyan")