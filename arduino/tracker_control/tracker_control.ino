/*
 ==============================================================================
 Project: ADS-B Tracking and Control System
 Author: Israel Brunini Oliveira
 GitHub: https://github.com/telec-rf
 License: GNU General Public License v3.0
 Version: 0.2

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program. If not, see <https://www.gnu.org/licenses/>.
 ==============================================================================
*/



// Motor de passo para PAN conectado nas portas D2 a D5
const int motor1Pins[4] = {2, 3, 4, 5}; 

// Motor de passo para TILT conectado nas portas D6 a D9
const int motor2Pins[4] = {6, 7, 8, 9}; 

// Sequência de passos (meia etapa) para 28BYJ-48 com ULN2003
const int steps[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1}
};

// Motor de passo para PAN conectado nas portas D2 a D5
const int motor1Pins[4] = {2, 3, 4, 5}; 

// Motor de passo para TILT conectado nas portas D6 a D9
const int motor2Pins[4] = {6, 7, 8, 9}; 

// Sequência de passos (meia etapa) para 28BYJ-48 com ULN2003
const int steps[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1}
};

const int stepDelay = 1; // Tempo entre passos (ms)

// Limite máximo de passos por eixo
const int maxPassosPan = 3940;   // Aproximadamente 350~360 graus
const int maxPassosTilt = 940;   // Aproximadamente 90 graus

// Passos por grau para cada eixo
const float passosPorGrauPan = maxPassosPan / 350.0;
const float passosPorGrauTilt = maxPassosTilt / 90.0;

int pos1 = 0; // posição da sequência do motor PAN (0 a 7)
int pos2 = 0; // posição da sequência do motor TILT (0 a 7)

float anguloPanAtual = 0.0;
float anguloTiltAtual = 0.0;

// Aplica um passo ao motor correspondente
void passoMotor(int motorPins[], int &pos, int dir) {
  pos += dir;
  if (pos > 7) pos = 0;
  if (pos < 0) pos = 7;

  for (int i = 0; i < 4; i++) {
    digitalWrite(motorPins[i], steps[pos][i]);
  }
}

// Movimento simultâneo com interpolação
void moverMotores(int passosPan, int passosTilt) {
  int dirPan = (passosPan >= 0) ? 1 : -1;
  int dirTilt = (passosTilt >= 0) ? 1 : -1;

  passosPan = abs(passosPan);
  passosTilt = abs(passosTilt);

  int maior = max(passosPan, passosTilt);
  int contPan = 0, contTilt = 0;

  for (int i = 0; i < maior; i++) {
    if ((long)contPan * maior / passosPan <= i && contPan < passosPan) {
      passoMotor(motor1Pins, pos1, dirPan);
      contPan++;
    }
    if ((long)contTilt * maior / passosTilt <= i && contTilt < passosTilt) {
      passoMotor(motor2Pins, pos2, dirTilt);
      contTilt++;
    }
    delay(stepDelay);
  }

  // Desliga bobinas após movimento
  for (int i = 0; i < 4; i++) {
    digitalWrite(motor1Pins[i], LOW);
    digitalWrite(motor2Pins[i], LOW);
  }
}

// Converte ângulos em passos e move motores
void moverGraus(float panDestino, float tiltDestino) {
  float deltaPan = panDestino - anguloPanAtual;
  float deltaTilt = tiltDestino - anguloTiltAtual;

  int passosPan = round(-deltaPan * passosPorGrauPan);   // sinal invertido!
  int passosTilt = round(-deltaTilt * passosPorGrauTilt); // sinal invertido!

  moverMotores(passosPan, passosTilt);

  anguloPanAtual = panDestino;
  anguloTiltAtual = tiltDestino;
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    pinMode(motor1Pins[i], OUTPUT);
    pinMode(motor2Pins[i], OUTPUT);
    digitalWrite(motor1Pins[i], LOW);
    digitalWrite(motor2Pins[i], LOW);
  }

  // Posiciona em ponto inicial arbitrário
  moverMotores(4000, 1400);
  moverMotores(0, -360);
}

void loop() {
  if (Serial.available()) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();

    if (comando.equalsIgnoreCase("status?")) {
      Serial.print("p:");
      Serial.print(anguloPanAtual, 1);
      Serial.print(",t:");
      Serial.println(anguloTiltAtual, 1);
    } 
    else if (comando.startsWith("p:") && comando.indexOf(",t:") != -1) {
      int indexP = comando.indexOf("p:") + 2;
      int indexT = comando.indexOf(",t:");

      String panStr = comando.substring(indexP, indexT);
      String tiltStr = comando.substring(indexT + 3);

      float pan = panStr.toFloat();
      float tilt = tiltStr.toFloat();

      if (pan >= 0 && pan <= 340.0 && tilt >= 0 && tilt <= 90.0) {
        moverGraus(pan, tilt);
      } else {
        Serial.println("err for limit");
      }
    } 
    else {
      Serial.println("Invalid command. Use: p:XX,t:YY or status?");
    }
  }
}
