from news.question import question

ARTICLE = """OpenAI et Meta annoncent le lancement de leurs intelligences artificielles capables de «raisonner»
Intelligence artificielle : de la fascination à l'inquiétudedossier
Dans la course à l’IA, OpenAI et Meta misent désormais sur des modèles capables de «réflexion», leur permettant par la même occasion de mener des tâches plus compliquées comme planifier et de réserver les différentes étapes d’un voyage.

(Michael Dwyer/AP)
par LIBERATION
publié le 10 avril 2024 à 14h32
Bientôt la liberté de penser ? OpenAI (ChatGPT) et Meta (Facebook, Instagram…) ont tous deux annoncé la sortie à venir de nouveaux modèles d’intelligence artificielle capables de «raisonner», selon le Financial Times. Nommés respectivement GPT-5 et Llama 3, les deux IA concurrentes n’ont pas encore de date de sortie précise, mais arriveraient «bientôt» pour la première. Pour la seconde, on parlerait de «quelques semaines».

A lire aussi
IA générale : «A l’heure actuelle, on ne parvient pas à faire une intelligence autonome»
Economie numérique
21 janv. 2024
«Nous travaillons dur pour trouver comment amener ces modèles non seulement à parler, mais aussi à raisonner et à planifier… à avoir de la mémoire», a annoncé Joelle Pineau, vice-présidente de la recherche en IA chez Meta. La prochaine génération de GPT d’OpenAI permettrait, elle, de résoudre des «problèmes difficiles», a expliqué Brad Lightcap, directeur des opérations d’OpenAI, au Financial Times.

Lors d’un événement à Londres ce mardi, Yann LeCun, chercheur en intelligence artificielle pour Meta, ne s’est pas montré tendre avec les IA actuelles. Selon lui, elles se contenteraient pour le moment de produire «un mot après l’autre sans réflexion», et «commettent toujours des erreurs stupides». Une intelligence artificielle plus aboutie serait quant à elle capable de raisonner, et de comprendre les conséquences de ses actions.

Parmi les exemples cités par le chercheur, un modèle plus poussé serait par exemple capable de planifier et de réserver les différentes étapes d’un voyage, rapporte le média anglais. Mais surtout, de telles avancées représenteraient un pas de plus vers «l’intelligence artificielle générale», le grand projet des adeptes du progrès à tout prix de la tech.

«L’intelligence artificielle générale » dangereuse ?
Abrégée «IAG» sa définition exacte reste floue, entre une IA à l’intelligence équivalente à la nôtre ou, pour certains, supérieure. Du côté d’OpenAI, on penche plutôt pour la deuxième option, avec la définition «système hautement autonome qui surpasse les humains dans le travail le plus économiquement rentable». Un objectif à atteindre à tout prix pour certains, mais une crainte immense pour d’autres.

Fin 2023, les membres du conseil d’administration de l’entreprise s’écharpaient sur la vision de leur dirigeant, Sam Altman, avide d’IA sorties parfois trop vite ou jugées trop puissantes – et de la fameuse intelligence artificielle générale. Brièvement évincé par un conseil d’administration plus frileux que lui en novembre dernier, son retour, porté par le soutien de ses employés, a marqué le tournant d’OpenAI vers une quête du progrès à tout prix – quitte à lever le pied sur une évolution raisonnable.

Depuis, OpenAI, Meta, Google et les autres acteurs du milieu se tirent la bourre à coups d’intelligences artificielles personnalisées et autres générateurs de vidéos en direct – à l’instar de Sora, capable de créer des extraits d’une minute après simple saisie de texte décrivant la scène demandée. Autant d’évolutions qui ont un coût : en février, Sam Altman demandait de réunir 7 000 milliards de dollars pour financer de nouvelles usines de semi-conducteurs, des composants essentiels pour faire fonctionner de puissantes IA.
"""

if __name__ == "__main__":
    answer = question(ARTICLE, "Est ce que cet article mentionne les DeepFakes? Yes or No")
    print(answer.answer)
    print(answer.reflexions)
    print(answer.explanations)
    print(answer.error_message)
    print(answer.full_answer)