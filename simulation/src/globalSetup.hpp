/*! \class GlobalSetup
	\brief Clase que contiene todas las variables de control
	\author Manuel Carlevaro <manuel@iflysib.unlp.edu.ar> 

	\version 1.0 Inicio del proyecto.

	\date 2024.08.05
	*/

#ifndef _GLOBALSETUP_H
#define _GLOBALSETUP_H

#include <cstdlib>
using std::exit;
#include <iostream>
using std::cout; using std::endl;
#include <fstream>
using std::ifstream;
#include <string>
using std::string;
#include <vector>
using std::vector;
#include <cmath>
using std::sin; using std::cos;
#include <iomanip>
using std::fixed; using std::setw;
#include <box2d/box2d.h>
#include <time.h>

#define PI 3.1415926

#define INFO(msg) \
    fprintf(stderr, "info: %s:%d: ", __FILE__, __LINE__); \
    fprintf(stderr, "%s\n", msg);

/** \struct Contenedor
 * \brief Estructura que almacena la información relativa a un contenedor de 
 * granos.
 * 
 * Estructura que almacena la información relativa a un contenedor de granos:
 * \li datos geométricos
 * \li información sobre el material
 * */
struct Contenedor {
	double R; /*!< Radio del contenedor */
    double H;  /*!< Altura de la rugosidad */
	double r; /*!< Radio del orificio de salida del contenedor */
	double theta; /*!< Inclinación del orificio de descarga*/
	double fric; /*!< Coeficiente de fricción del contenedor (paredes) */
	double rest; /*!< Coeficiente de restitución del contenedor */
    double muBase; /*!< Coeficiente de fricción de los granos con las paredes
                     anterior y posterior (ficticia) */
    b2Vec2 n_out; /*!< Versor normal hacia afuera del orificio de descarga */
    double y_max_hole; /*!< Altura máxima del orificio de salida */
};

/** \struct tipoGrano
 * \brief Estructura que contiene información sobre un determinado tipo de granos
 * 
 * Estructura que contiene información sobre un determinado tipo de grano:
 * \li datos geométricos
 * \li información sobre el material que lo compone
 * */
struct tipoGrano {
	int noGranos;	/*!< Cantidad de granos de este tipo */
	double radio;	/*!< Radio */
	int nLados;		/*!< Número de lados (1: círculo) */
	double **vertices;	/*!< Array con coordenadas de los vértices (double x, double y) */
	double dens; /*!< Densidad de los granos */
	double fric; /*!< Coeficiente de fric de los granos */
	double rest; /*!< Coeficiente de restitución de los granos */
};

/** \struct bodyData
 * \brief Estructura que almacena datos asociados a cada grano.
 * */
struct BodyData {
    int tipo; /*!< Tipo de grano (en el orden en que aparecen en el .in */
	bool isGrain;	/*!< Variable lógica que identifica granos */
    bool isIn; /*!< Variable lógica que identifica granos dentro del contenedor */
	int nLados;	/*!< Número de lados que tiene el grano */
	int gID; /*!< Identificador del grano */
};

/** \class GlobalSetup
 * Clase que contiene toda la información necesaria para realizar una simulación
 * */
class GlobalSetup {
public:
// Parámetros de objetos del modelo
	Contenedor caja; /*!< Recinto de contención */
	int noTipoGranos; /*!< Cantidad de tipos de granos distintos en la simulación */
	tipoGrano **granos; /*!< Array que contiene los distintos tipos de granos */
	bool isBullet; /*!< Define si los granos se tratan como bullet (T) o no (F) */

// Parámetros de control de la simulación
	double tStep; /*!< Paso temporal de integración */
	double tMax; /*!< Límite temporal de la simulación */
	double tFill; /*!< Tiempo de llenado antes de retirar la tapa */
	int pIter; /*!< Iteraciones para la satisfacción de restricciones de posición */
	int vIter; /*!< Iteraciones para la satisfacción de restricciones de velocidad */
	double g; /*!< Aceleración de la gravedad */
    bool reinyect; /*!< True si los granos se reinyecta, false si se eliminan */
    double tiempoEsperaAtasco; /*!< Tiempo de espera para remover un atasco */
	int maxAvalanchas; /*!< Número máximo de avalanchas permitidas */
	double Rmedio; /*!< Radio medio de los granos (promedio ponderado) */

// Parámetros de estadísticas y registros
    string dirID; /*!< Identificador del directorio de archivos de frames de modo
                        que no se pisen. */
	int saveFrameFreq; /*!< Frecuencia de guardado de frames */
	string preFrameFile; /*!< Prefijo del nombre del archivo de salida de frame/trayectoria */
	int fluxFreq; /*!< Frecuencia de observación del flujo */
	string fluxFile; /*!< Prefijo del nombre del archivo de salida de flujo */
    int q6_freq; /*!< Frecuencia de guardado de Q6 */
    int pf_freq; /*!< Frecuencia de guardado del packing fraction */
	int veFreq; /*!< Frecuencia de observación de velocidades y energía */
	string veFile; /*!< Prefijo del nombre del archivo de salida v/E */
    int saveContactFreq; /*!< Frecuencia de guardado de fuerzas de contacto */
    double tStartCF, tEndCF; /*!< Tiempo de inicio y final de guardado de 
                               fuerzas de contacto */


// Constructor & destructor
	GlobalSetup(string input);
	~GlobalSetup();

// Info
	void printGlobalSetup();
	string inputFile; /*!< Nombre del archivo que contiene los parámetros de ejecución */
	//ModeOut modeOut; [>!< Define el modo de salida de la información <]
	unsigned int randomSeed; /*!< Semilla del generador de números aleatorios */

private:
	void load(string iFile);
};

#endif

