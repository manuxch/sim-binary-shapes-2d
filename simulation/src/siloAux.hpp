/*! \file siloAux.hpp
 * \brief Archivo de cabecera para funciones auxiliares
 *
 * \author Manuel Carlevaro <manuel@iflysib.unlp.edu.ar>
 * \version 1.0
 * \date 2024.08.05
 */

#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <box2d/box2d.h>
#include "globalSetup.hpp"
#include <cmath>
using std::sqrt; using std::sin; using std::cos; using std::atan2;
#include <gsl/gsl_sf_legendre.h>
#include <iostream>
//#include <CGAL/Exact_predicates_exact_constructions_kernel.h>
//#include <CGAL/Delaunay_triangulation_2.h>
//#include <CGAL/Voronoi_diagram_2.h>

//typedef CGAL::Exact_predicates_exact_constructions_kernel Kernel;
//typedef CGAL::Delaunay_triangulation_2<Kernel> DT;
//typedef CGAL::Voronoi_diagram_2<Kernel, DT> VoronoiDiagram;
//typedef VoronoiDiagram::Face_handle FaceHandle;
//typedef VoronoiDiagram::Face_iterator FaceIterator;
//typedef VoronoiDiagram::Ccb_halfedge_circulator CcbHalfedgeCirculator;
//typedef VoronoiDiagram::Dual Dual;
//typedef Dual::Face_handle DualFaceHandle;
//typedef Dual::Face_iterator DualFaceIterator;

extern GlobalSetup *globalSetup;

/*! Convierte un número en una string de ancho fijo
 * y rellena de ceros, para enumerar frames secuencialmente
 * \param int num
 * \return std::string
 */
std::string int2str(int num);

/*! Detecta si el sistema está activo
 * \param b2World* w 
 * \return bool
 */
bool isActive(b2World *w);

/*! Escribe en el archivo de salida las coordenadas de las partículas
 * \param b2Word* w
 * \param int file_ID
 * \param GlobalSetup* parámetros globales
 * \return void
 */
void savePart(b2World *w, int file_id, const GlobalSetup *globalSetup);

/*! Escribe todas las coordenadas necesarias para generar imágenes
 * y posteriores animaciones
 * \param b2World* w
 * \param int frm_id
 * \param GlobalSetup* parámetros globales
 * \return void
 */
void saveFrame(b2World *w, int frm_id, const GlobalSetup *globalSetup);

/*! Devuelve la cantidad de granos descargados
 * \param b2World* w
 * \param int* st (suma por tipo de granos)
 * \param paso paso actual de la simulación
 * \param ofstream archivo de salida del flujo
 * \param GlobalSetup* parámetros globales
 * \return int
 */
int countDesc(b2World *w, int *st, int paso,
        std::ofstream &fluxFile, const GlobalSetup* gs);

/*! Imprime las velocidades y energías
 * \param float timeS : tiempo de la simulación
 * \param b2Word* w : mundo
 * \param GlobalSetup* parámetros globales
 * \return void
 */
void printVE(int frm_id, float timeS, b2World *w, const GlobalSetup* gs);

/*! \fn saveContacts
 * \brief Guarda las fuerzas de contacto normal y tangencial
 * \param b2World* : mundo
 * \param float : time step
 * \param int : file ID
 * \param GlobalSetup* parámetros globales
 * */
void saveContacts(b2World *w, float ts, int file_id, 
        const GlobalSetup *globalSetup);

/*! \fn saveQ6
 * \brief Guarda las posiciones de los granos y sus
 * valores de Q6.
 * \param b2World* : mundo
 * \param float : time step
 * \param int : file ID
 * \param GlobalSetup* parámetros globales
 * */
void saveQ6(b2World *w, int file_id, const GlobalSetup *globalSetup);

/*! \fn savePF
 * \brief Guarda las posiciones de los granos y sus
 * valores de packing fraction local.
 * \param b2World* : mundo
 * \param float : time step
 * \param int : file ID
 * \param GlobalSetup* parámetros globales
 * */
//void savePF(b2World *w, int file_id, const GlobalSetup *globalSetup);


