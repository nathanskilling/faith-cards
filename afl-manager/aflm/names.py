"""Name pools for randomly generated (entirely fictional) players."""

FIRST_NAMES = """
Jack Tom Josh Sam Will Harry Lachie Liam Noah Ben Luke Max Jake Zac Matt Nick
Charlie Ollie James Dan Ryan Jordan Mitch Connor Riley Bailey Cooper Jesse Tyler
Brodie Callum Darcy Hamish Angus Archie Hugo Xavier Finn Jai Kai Koby Jye Kade
Blake Brayden Caleb Cam Corey Dylan Ed Eli Ethan Flynn Fraser George Hayden Heath
Isaac Jarrod Jayden Joel Kane Kyle Lewis Logan Louis Marcus Mason Nathan Ned Oscar
Paddy Patrick Reece Rhys Rory Scott Sean Seb Shaun Taj Tim Toby Trent Zane Aaron
Adam Alex Andrew Anthony Ash Beau Billy Brad Brandon Brent Chad Chris Clay Cody
Dane Dean Dom Elliot Gus Harley Harvey Jacob Jared Jarrah Jed Judd Kieran Lenny
Leo Levi Malcolm Marty Miles Nash Nate Nic Otis Perry Quinn Reuben Rex Robbie Sid
Sonny Tex Theo Tobias Tristan Ty Wade Wil Zeke Arlo Banjo Bodhi Clancy Digby
Fletcher Jarman Kobe Lachlan Mac Matty Maverick Murphy Remy Sullivan Tanner
Malakai Tyrell Jeremiah Isaiah Elijah Giovanni Luca Matteo Dante Marco
Christian Stefan Nikolas Kosta Andreas Mihail Tariq Bilal Adem Hussein Deng
Akec Garang Thon Jarrah Kirra Minh Arjun Ravi Tevita Sione Manu
""".split()

LAST_NAMES = """
Smith Jones Williams Brown Wilson Taylor Johnson White Martin Anderson Thompson
Walker Harris Lee Ryan Robinson Kelly King Davis Wright Evans Roberts Green Hall
Wood Jackson Clarke Scott Turner Hill Moore Cooper Ward Morris Watson Mitchell
Campbell Young Edwards Stewart Parker Collins Bennett Murphy Cook Bailey Bell
Richardson Cox Howard Hughes Gray Reid Murray Kennedy Graham Sullivan Marshall
Henderson Ross Ferguson Hamilton Grant Simpson Fraser Cameron McDonald Macdonald
Crawford Douglas Burns Gordon Shaw Hunter Dunn Black Lawson Duncan Walsh Byrne
O'Brien O'Connor O'Neill O'Sullivan Doyle Brennan Burke Gallagher Quinn Nolan
Fitzgerald Flanagan Hogan Keane Maguire Sheehan Tierney Whelan Rowe Pearce Baxter
Hodge Lynch Dempsey Carroll Daly Egan Farrell Hayes Kerr Lowe Mills Nash Payne
Rhodes Saunders Tanner Vaughan Webb York Atkins Barlow Carter Dawson Ellis Fox
Gibson Holmes Ingram Jenkins Knight Lang Mason Norris Oliver Perry Radford Sharp
Tucker Vickery Weller Archer Bolton Chapman Dixon English Fletcher Garner Hardy
Jarvis Keating Lloyd Mercer Newman Ogden Porter Rankin Stanton Thorne Underwood
Rossi Russo Ferrari Romano Colombo Ricci Marino Greco Bruno Conti Costa
Mancini Lombardi Moretti Barbieri Galli Rinaldi Caruso Vitale Santoro De_Luca
Papadopoulos Georgiou Nikolaou Dimitriou Kostas Pappas Stavros Vasilakis
Nguyen Tran Pham Chen Wong Lim Tan Singh Patel Kumar Ali Hassan Haddad Khoury
Mayom Akol Kuol Wek Majok Taumalolo Fifita Havili Tuipulotu
Collard Bennell Coolwell Hayward Walley Dann Coyne Thorpe Briggs Moran
Vandenberg De_Boer Janssen Visser Kowalski Nowak Novak Petrovic
Jovanovic Horvat Kovac Schmidt Muller Weber Fischer Larsen Hansen Nielsen
McKenzie McLean McGregor McIntosh McCarthy McGrath McKay McPherson McInnes
MacKenzie Sinclair Dalgleish Abernethy Drummond Lockhart Paterson Ramsay
Whitlock Ashcroft Pennington Harrington Castellano Bradshaw Winterton Hollis
""".split()

# De-duplicate (keeping order) and restore spaces in multi-word surnames.
FIRST_NAMES = list(dict.fromkeys(FIRST_NAMES))
LAST_NAMES = [n.replace("_", " ") for n in dict.fromkeys(LAST_NAMES)]
