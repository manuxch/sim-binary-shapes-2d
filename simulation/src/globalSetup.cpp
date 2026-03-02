#include "globalSetup.hpp"

/*! \fn GlobalSetup::GlobalSetup(string iFile)
	Constructor de la clase GlobalSetup */
GlobalSetup::GlobalSetup(string iFile): inputFile(iFile)  {
	load(iFile);
	printGlobalSetup();
    // Cálculo del versor n_out:
    double theta_rad = caja.theta * PI / 180.0;  // theta en RADIANES
    caja.n_out.Set(2 * caja.r * cos(theta_rad), caja.r * sin(theta_rad));
    caja.n_out.Set(caja.r * sin(theta_rad), -2 * caja.r * cos(theta_rad));
    caja.n_out.Normalize();
    // Cálculo de la altura máxima del orificio de salida:
    caja.y_max_hole = 2.0 * caja.r * sin(theta_rad);
}

/*! \fn ~GlobalSetup::GlobalSetup()
	Destructor de la clase GlobalSetup
	*/
GlobalSetup::~GlobalSetup() {
	for (int i = 0; i < noTipoGranos; i++) {
		if (granos[i]->nLados > 1) {
			for (int j = 0; j < granos[i]->nLados; j++) {
				delete [] granos[i]->vertices[j];
			}
			delete granos[i]->vertices;
		}
	}
	delete [] granos;
}


void GlobalSetup::load(string inputFile){
	ifstream fin(inputFile.c_str());
	string ident;
	
	if (!fin.is_open()) {
		cout << "ERROR: No se puede abrir el archivo " << inputFile << endl;
		exit(1);
	}

	tiempoEsperaAtasco = 0.0; // por defecto
	maxAvalanchas = 0; // por defecto: sin límite

	while (!fin.eof()) {
		fin >> ident;

        // Lectura de parámetros del contenedor
        //
		if (ident == "Radio_silo:") {
			fin >> caja.R;
			if (caja.R <= 0) {
				cout << "ERROR: El radio de la caja debe ser > 0." << endl;
				exit(1);
			}
		}
		if (ident == "H:") {
			fin >> caja.H;
            if (caja.H < 0.0) {
                cout << "ERROR: El valor de H debe ser >= 0." << endl;
                exit(1);
            }
		}
		if (ident == "Radio_salida:") {
			fin >> caja.r;
			if (caja.r <= 0) {
				cout << "ERROR: El valor del radio del orificio debe ser > 0." 
                     << endl;
				exit(1);
			}
		}
        if (ident == "theta:") {
            fin >> caja.theta;
            if (caja.theta < 0.0 || caja.theta > 170.0) {
                cout << "ERROR: Theta debe ser -90 <= theta <= 90." << endl;
                exit(1);
            }
        }
		if (ident == "Silo_fric:") {
			fin >> caja.fric;
			if (caja.fric <= 0) {
				cout << "El coeficiente de fricción de la caja debe ser > 0." 
                     << endl;
				exit(1);
			}
		}
		if (ident == "Silo_rest:") {
			fin >> caja.rest;
			if (caja.rest <= 0) {
				cout << "ERROR: El coeficiente de restitución debe ser > 0." 
                     << endl;
				exit(1);
			}
		}

		if (ident == "Silo_muBase:") {
			fin >> caja.muBase;
			if (caja.rest < 0) {
				cout << "ERROR: El coeficiente de fricción 'ficticio' ser >= 0." 
                     << endl;
				exit(1);
			}
		}
        // Fin parámetros del contenedor
        //
        // Lectura de parámetros de los granos
        //
		if (ident == "noTipoGranos:") {
			fin >> noTipoGranos;
			if (noTipoGranos <= 0) {
				cout << "ERROR: El número de tipos granos debe ser > 0." 
                     << endl;
				exit(1);
			}
			granos = new tipoGrano*[noTipoGranos];
			for (int i = 0; i < noTipoGranos; i++) {
				granos[i] = new tipoGrano;
				fin >> granos[i]->noGranos;
				fin >> granos[i]->radio;
				fin >> granos[i]->nLados;
				fin >> granos[i]->dens;
				fin >> granos[i]->fric;
				fin >> granos[i]->rest;
				if (granos[i]->noGranos < 1) {
				cout << "ERROR: El número de granos debe ser > 0." << endl;
				exit(1);
				}
				if (granos[i]->radio < 0.01) {
				cout << "ERROR: El radio de los granos debe ser > 0.01" << endl;
				exit(1);
				}
				if ((granos[i]->nLados != 1) && 
                        (granos[i]->nLados < 1 || granos[i]->nLados > 8)) {
				            cout << "ERROR: El número de lados debe ser 1 o 2 ";
                            cout << "< nLados < 8." << endl;
				exit(1);
				}
				if (granos[i]->dens <= 0) {
					cout << "ERROR: La densidad de los granos debe ser > 0." 
                        << endl;
					exit(1);
				}
				if (granos[i]->fric< 0.0) {
					cout << "ERROR: El coeficiente de rozamiento debe ser ";
                    cout << "0 <= rozam." << endl;
					exit(1);
				}
				if (granos[i]->rest < 0.0 || granos[i]->rest > 1.0) {
					cout << "ERROR: El coeficiente de restitución debe ser ";
                    cout << "0 <= rest <= 1.0." << endl;
					exit(1);
				}
				if (granos[i]->nLados > 1) {
					granos[i]->vertices = new double*[granos[i]->nLados];
					double x,y,theta;
					theta = 2.0*3.141592653589793/granos[i]->nLados;
					for (int j = 0; j < granos[i]->nLados; j++) {
						x = granos[i]->radio*cos(j*theta); 
						y = granos[i]->radio*sin(j*theta); 
						granos[i]->vertices[j] = new double[2];
						granos[i]->vertices[j][0] = x;
						granos[i]->vertices[j][1] = y;
					}
				}
			}
		    // === NUEVO: cálculo de Rmedio ===
			double sumR = 0.0;
			int sumN = 0;

			for (int i = 0; i < noTipoGranos; ++i) {
				sumR += granos[i]->radio * granos[i]->noGranos;
				sumN += granos[i]->noGranos;
			}

			if (sumN > 0) {
				Rmedio = sumR / (double)sumN;
			} else {
				// fallback defensivo (nunca deberías caer acá si el input está bien)
				Rmedio = 0.01;	
		}
	}
        // Fin parámetros de granos
        //
        // Lectura de parámetros de control
        //
		if (ident == "timeStep:") {
			fin >> tStep;
			if (tStep < 0.0) {
				cout << "ERROR: El paso de integración debe ser >= 0." << endl;
				exit(1);
			}
		}
		if (ident == "tMax:") {
			fin >> tMax;
			if (tMax < 0.0) {
				cout << "ERROR: el tiempo máximo de simulación debe ser > 0." 
                     << endl;
				exit(1);
			}
		}
		if (ident == "tEsperaAtasco:") {
			fin >> tiempoEsperaAtasco;
			if (tiempoEsperaAtasco < 0.0) {
				cout << "ERROR: tEsperaAtasco debe ser >= 0." << endl;
				exit(1);
			}
		}
		if (ident == "maxAvalanchas:") {
			fin >> maxAvalanchas;
			if (maxAvalanchas < 0) {
				cout << "ERROR: maxAvalanchas debe ser >= 0." << endl;
				exit(1);
			}
		}
        if (ident == "tFill:") {
            fin >> tFill;
            if (tMax < 0.0) {
                cout << "ERROR: el tiempo de llenado debe ser > 0." << endl;
                exit(1);
            }
        }
		if (ident == "pIter:") {
			fin >> pIter;
			if (pIter < 0) {
				cout << "ERROR: El número de iteraciones de posicion debe ser ";
                cout << " > 0." << endl;
				exit(1);
			}
		}
		if (ident == "vIter:") {
			fin >> vIter;
			if (vIter < 0) {
				cout << "ERROR: El número de iteraciones de velocidad debe ser";
                cout << " > 0." << endl;
				exit(1);
			}
		}
		if (ident == "g:") {
			fin >> g;
		}
        if (ident == "Reinyected:") {
            string rein;
            fin >> rein;
            reinyect = (rein == "T" ? true : false);
            if (reinyect && tMax < tStep) {
                cout << "ERROR: tMax debe ser > tStep cuando se reinyecta." << endl;
                exit(1);
            }
        }
        if (ident == "Bullets:") {
            string bull;
            fin >> bull;
            isBullet = (bull == "T" ? true : false);
        }
        if (ident == "RandomSeed:") {
            fin >> randomSeed;
        }
        if (ident == "preFrameFile:") {
            fin >> preFrameFile;
        }
        if (ident == "fluxFile:") {
            fin >> fluxFile;
        }
        if (ident == "saveFrameFreq:") {
            fin >> saveFrameFreq;
            if (saveFrameFreq < 0) {
            cout << "ERROR: la frecuencia de guardado debe ser >= 0." << endl;
            exit(1);
            }
        }
        if (ident == "fluxFreq:") {
            fin >> fluxFreq;
            if (fluxFreq < 0) {
                cout << "ERROR: la frecuencia de guardado del flujo debe ser ";
                cout << ">= 0." << endl;
                exit(1);
            }
        }
        if (ident == "Q6_Freq:") {
            fin >> q6_freq;
            if (q6_freq < 0) {
                cout << "ERROR: la frecuencia de guardado de Q6 debe ser ";
                cout << ">= 0." << endl;
                exit(1);
            }
        }
        if (ident == "PF:") {
            fin >> pf_freq;
            if (pf_freq < 0) {
                cout << "ERROR: la frecuencia de guardado del packing fraction debe ser ";
                cout << ">= 0." << endl;
                exit(1);
            }
        }
        if (ident == "VE_freq:") {
            fin >> veFreq;
            if (veFreq < 0) {
                cout << "ERROR: la frecuencia de guardado de velocidades y "
                    << "energías debe ser >= 0." << endl;
                exit(1);
            }
        }
        if (ident == "veFile:") {
            fin >> veFile;
        }

        else if (ident == "dirID:") {
            fin >> dirID;
        }

        else if (ident == "saveForcesFreq:") {
            fin >> saveContactFreq;
        }

        else if (ident == "tStartCF:") {
            fin >> tStartCF;
        }

        else if (ident == "tEndCF:") {
            fin >> tEndCF;
        }
	} //fin bucle de lectura de inputFile
} // Fin función load()

/*! \fn GlobalSetup::printGlobalSetup()
	Función que imprime las variables contenidas en GlobalSetup
	*/
 void GlobalSetup::printGlobalSetup() {
	cout << "# Lectura de los parámetros de entrada ..." << endl;
	cout << "#  Archivo de parámetros: " << inputFile << endl;
	cout << "# Parámetros de los objetos" << endl;
    cout << "# \t Radio del silo: " << caja.R << " [m]" << endl;
    cout << "# \t Radio del orificio de salida: " << caja.r << " [m]" << endl;
    cout << "# \t Ángulo de inclinación del plano de salida: " << caja.theta << " grados." 
         << endl;
    cout << "# \t   H: " << caja.H << " [m]" << endl;
    cout << "# \t Coeficiente de fricción de la caja (paredes): " 
        << caja.fric << endl;
    cout << "# \t Coeficiente de restitución de la caja: " << caja.rest << endl;
    cout << "# \t Coeficiente de fricción 'ficticio': " << caja.muBase << endl;
	cout << "#  Parámetros de los granos:" << endl;
	cout << "# \t Número de tipos de granos: " << noTipoGranos << endl;
	cout << "# \t Radio medio de grano: " << Rmedio << " [m]" << endl;
	for (int i = 0; i < noTipoGranos; i++) {
		cout << "# \t Grano tipo " << i + 1 << ":" << endl;
		cout << "# \t   Número de granos: " << granos[i]->noGranos << endl;
		cout << "# \t   Radio = " << granos[i]->radio << " [m]" << endl;
		cout << "# \t   Densidad = " << granos[i]->dens << " [kg/m²]" << endl;
		cout << "# \t   Coeficiente de fricción = " << granos[i]->fric << endl;
		cout << "# \t   Coeficiente de restitución = " << granos[i]->rest 
             << endl;
		cout << "# \t   Geometría: ";
		if (granos[i]->nLados == 1) cout << "Disco." << endl;
		else {
			cout << "# Polígono de " << granos[i]->nLados << " lados." << endl;
			cout <<"# \t   Vértices: " << endl;
			for (int j = 0; j < granos[i]->nLados; j++) {
				cout << "# \t\t(" << fixed << setw(4) 
                     << granos[i]->vertices[j][0] << ", " << fixed << setw(4) 
                     << granos[i]->vertices[j][1] << "), " << endl;
			}
		}
	}
	cout << "# Parámetros de control:" << endl;
	cout << "# \t Paso de integración: " << tStep << " s."<< endl;
	cout << "# \t Tiempo máximo de simulación: " << tMax << " s." << endl;
	cout << "# \t Tiempo de llenado del silo: " << tFill << " s." << endl;
	cout << "# \t Tiempo de espera para remover atascos: "
		<< tiempoEsperaAtasco
		<< " s." << endl;

	if (maxAvalanchas > 0) {
		cout << "# \t Número máximo de avalanchas permitidas: "
			<< maxAvalanchas << endl;
	} else {
		cout << "# \t Número máximo de avalanchas permitidas: sin límite."
			<< endl;
	}
	cout << "# \t Iteraciones para restricciones de posición: " << pIter << endl;
	cout << "# \t Iteraciones para restricciones de velocidad: " << vIter 
         << endl;
	cout << "# \t Aceleración de la gravedad: " << g << " m/s²." << endl;
    cout << "# \t Granos que salen son " 
        << (reinyect ? "reinyectados." : "eliminados.") << endl;
    cout << "# \t Granos considerados bullet? " << (isBullet ? "Si." : "No.") 
         << endl;
    cout << "# \t Semilla del generador de números aleatorios: " 
         << randomSeed << endl;
	cout << "# Parámetros de estadísticas y registros:" << endl;
    cout << "#\t Identificador de carpeta y archivos: " << dirID << endl;
    cout << "# \t Prefijo de archivos de frames: " << preFrameFile << endl;
    cout << "# \t Frecuencia de guardado de frames: " << saveFrameFreq << endl;
    cout << "# \t Frecuencia de guardado de Q6: " 
            << (q6_freq ? std::to_string(q6_freq) : "No se guarda.") << endl;
    cout << "# \t Frecuencia de guardado de packing fraction: " 
            << (pf_freq ? std::to_string(pf_freq) : "No se guarda.") << endl;
    cout << "# \t Prefijo de archivo de flujo: " << fluxFile << endl;
    cout << "# \t Frecuencia de guardado de flujo: " << fluxFreq << endl;
    cout << "# \t Frecuencia de guardado de velocidades y energías : " 
            << veFreq << endl;
    if (veFreq > 0)
        cout << "# \t Archivo de guardado de velocidades y energías: " 
             << veFile << endl;
    cout << "#\t Frecuencia de guardado de contactos y fuerzas: " 
         << saveContactFreq << endl;
    cout << "#\t Inicio de registro de fuerzas de contacto: " << tStartCF 
         << " s." << endl;
    cout << "#\t Fin de registro de fuerzas de contacto: " << tEndCF 
         << " s." << endl;
	cout << "# ... lectura de parámetros de entrada finalizada." << endl;
}
